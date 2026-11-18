#!/usr/bin/env python3
"""Run the grasp contact probe: pre-registered trials, one headless gz-sim per trial.

Everything the run depends on is written next to the data (world.sdf, meta.json,
protocol.json, plugin sha256) so a trial can be replayed and audited without
trusting this script.

The probe is deliberately narrow: a force-limited parallel jaw closes on a rigid
box, lifts 0.15 m, holds 0.5 s, and records the object pose relative to the
gripper every 1 ms physics step. Nothing attaches the object to the gripper.

Usage:
  python3 run_probe.py --stage acceptance [--out results/<id>] [--rebuild]
  python3 run_probe.py --stage stress
  python3 run_probe.py --stage smoke --only 1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

NL = chr(10)
ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "worlds" / "grasp_probe.sdf.tmpl"
BUILD = ROOT / "build"
PLUGIN = BUILD / "libflexcell_grasp_probe.so"

# Pre-registered protocol. Thresholds are copied verbatim into protocol.json and
# must not be edited after the first run; analyse.py reads them, it never
# decides them.
PROTOCOL = {
    "schema_version": 1,
    "kind": "GRASP_CONTACT_PROBE",
    "question": "Can a parallel jaw hold and lift a rigid box with contact friction alone?",
    "physics": {"engine": "gz-sim 8 dartsim", "step_s": 0.001},
    "rig": {"open_gap_m": 0.056, "closed_gap_m": 0.020, "lift_height_m": 0.15},
    "phases_s": {"settle": 0.30, "close": 0.40, "lift": 0.50, "hold": 0.50},
    "control": {
        "finger_servo": "Force = clamp(kp*(q_target-q) - kd*qd, +/-max_force)",
        "kp_finger": 1000.0,
        "kd_finger": 20.0,
        "max_finger_force_n": 20.0,
        "kp_lift": 4000.0,
        "kd_lift": 80.0,
        "max_lift_force_n": 80.0,
    },
    "acceptance": {
        "reference": "mean rel pose over the last 50 ms of the close phase",
        "drift_translation_mm_max": 2.0,
        "drift_rotation_deg_max": 5.0,
        "drop_relative_z_mm": -20.0,
        "drop_abs_drift_mm": 30.0,
        "trials_required_pass": 10,
        "objects": ["box_a", "box_b"],
    },
    "trials_per_object": 5,
    # Declared up front so a later edit of meta.json is detectable from protocol.json.
    "object_specs": {
        "box_a": {"size_m": 0.035, "mass_kg": 0.05, "mu": 1.0},
        "box_b": {"size_m": 0.050, "mass_kg": 0.12, "mu": 1.0},
    },
    # Controls, not part of the acceptance verdict: they exist to prove the probe
    # can fail. A probe that only ever passes proves nothing about friction.
    "controls": {
        "slip_expected": {"mu": 0.20, "mass_kg": 0.50,
                          "why": "2*mu*N = 2*0.2*7.5 = 3.0 N < m*(g+a) = 6.7 N"},
        "load_ladder_kg": [0.50, 1.00, 1.20, 1.50],
        "load_ladder_prediction": "slip above m = 2*mu*N/(g+a) = 15.0/13.4 = 1.12 kg",
    },
}

# Deterministic jitter: a real grasp never lands exactly centred. Values are
# fixed up front so the 5+5 trial set is not chosen after seeing the results.
JITTER = [
    {"x": 0.0000, "y": 0.0000, "yaw_deg": 0.0},
    {"x": 0.0015, "y": 0.0000, "yaw_deg": 1.5},
    {"x": -0.0015, "y": 0.0008, "yaw_deg": -1.5},
    {"x": 0.0008, "y": -0.0012, "yaw_deg": 2.0},
    {"x": -0.0008, "y": 0.0012, "yaw_deg": -2.0},
]

OBJECTS = {
    "box_a": {"size_m": 0.035, "mass_kg": 0.05, "mu": 1.0},
    "box_b": {"size_m": 0.050, "mass_kg": 0.12, "mu": 1.0},
}

# Load ladder shared by the contact controls and the magnet baseline, so both
# rows of the comparison table refer to the same payloads.
MAGNET_LADDER_KG = (0.05, 0.50, 1.00, 1.20, 1.50, 2.00, 5.00)


def trial_specs(stage: str) -> list[dict]:
    trials: list[dict] = []
    if stage in ("acceptance", "smoke"):
        for name, props in OBJECTS.items():
            for index, jitter in enumerate(JITTER):
                trials.append({
                    "trial": f"{name}-{index + 1:02d}",
                    "group": "acceptance",
                    "object_name": name,
                    "size_m": props["size_m"],
                    "mass_kg": props["mass_kg"],
                    "mu": props["mu"],
                    "jitter": jitter,
                    "lift_s": PROTOCOL["phases_s"]["lift"],
                })
        if stage == "smoke":
            trials = trials[:1]
    elif stage == "stress":
        # Exploratory only: not part of the 10/10 acceptance verdict.
        variants = [
            ("load-0.05kg", {"mass_kg": 0.05}),
            ("load-0.50kg", {"mass_kg": 0.50}),
            ("load-1.00kg", {"mass_kg": 1.00}),
            ("load-1.20kg", {"mass_kg": 1.20}),
            ("load-1.50kg", {"mass_kg": 1.50}),
            ("load-2.00kg", {"mass_kg": 2.00}),
            ("load-5.00kg", {"mass_kg": 5.00}),
            ("mu-0.20-mass-500g", {"mu": 0.20, "mass_kg": 0.50}),
            ("fast-lift-1ms", {"lift_s": 0.15}),
            ("thin-20mm", {"size_m": 0.020, "mass_kg": 0.03}),
        ]
        for name, overrides in variants:
            props = {"size_m": OBJECTS["box_a"]["size_m"], "mass_kg": OBJECTS["box_a"]["mass_kg"],
                     "mu": OBJECTS["box_a"]["mu"]}
            props.update(overrides)
            trials.append({
                "trial": f"stress-{name}",
                "group": "stress",
                "object_name": "box_a",
                "size_m": props["size_m"],
                "mass_kg": props["mass_kg"],
                "mu": props["mu"],
                "jitter": JITTER[0],
                "lift_s": props.get("lift_s", PROTOCOL["phases_s"]["lift"]),
            })
    elif stage == "magnet":
        # Same rig, same ladder, but the object is carried by a detachable joint
        # instead of contact. Fingers never close, so no pad can touch it.
        for mass in MAGNET_LADDER_KG:
            trials.append({
                "trial": f"magnet-{mass:.2f}kg".replace(".", "-"),
                "group": "magnet",
                "mode": "magnet",
                "object_name": "box_a",
                "size_m": OBJECTS["box_a"]["size_m"],
                "mass_kg": mass,
                "mu": OBJECTS["box_a"]["mu"],
                "jitter": JITTER[0],
                "lift_s": PROTOCOL["phases_s"]["lift"],
            })
    else:
        raise SystemExit(f"unknown stage: {stage}")
    return trials


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_plugin(rebuild: bool) -> None:
    if PLUGIN.exists() and not rebuild:
        return
    BUILD.mkdir(parents=True, exist_ok=True)
    configure = subprocess.run(
        ["cmake", "-S", str(ROOT), "-B", str(BUILD), "-DCMAKE_BUILD_TYPE=Release"],
        capture_output=True, text=True)
    if configure.returncode != 0:
        raise SystemExit("cmake configure failed:\n" + configure.stdout[-4000:] + configure.stderr[-4000:])
    build = subprocess.run(["cmake", "--build", str(BUILD), "-j", "6"], capture_output=True, text=True)
    if build.returncode != 0:
        raise SystemExit("cmake build failed:\n" + build.stdout[-6000:] + build.stderr[-6000:])


def render_world(spec: dict, log_path: Path) -> str:
    text = TEMPLATE.read_text()
    inertia = spec["mass_kg"] / 12.0 * (2.0 * spec["size_m"] ** 2)
    magnet_block = ""
    if spec.get("mode") == "magnet":
        magnet_block = (
            "      <plugin filename='gz-sim-detachable-joint-system' "
            "name='gz::sim::systems::DetachableJoint'>" + NL +
            "        <parent_link>base_link</parent_link>" + NL +
            f"        <child_model>{spec['object_name']}</child_model>" + NL +
            "        <child_link>link</child_link>" + NL +
            "        <attach_topic>/probe/magnet/attach</attach_topic>" + NL +
            "        <detach_topic>/probe/magnet/detach</detach_topic>" + NL +
            "        <output_topic>/probe/magnet/state</output_topic>" + NL +
            "      </plugin>")
    values = {
        "@LOG_PATH@": str(log_path),
        "@MODE@": spec.get("mode", "contact"),
        "@MAGNET_BLOCK@": magnet_block,
        "@OBJECT_NAME@": spec["object_name"],
        "@OBJECT_SIZE@": f"{spec['size_m']:.6f}",
        "@OBJECT_MASS@": f"{spec['mass_kg']:.6f}",
        "@OBJECT_I@": f"{inertia:.12e}",
        "@OBJECT_X@": f"{spec['jitter']['x']:.6f}",
        "@OBJECT_Y@": f"{spec['jitter']['y']:.6f}",
        "@OBJECT_YAW@": f"{spec['jitter']['yaw_deg'] * 3.141592653589793 / 180.0:.9f}",
        "@OBJECT_Z@": f"{spec['size_m'] / 2.0:.6f}",
        "@MU@": f"{spec['mu']:.3f}",
        "@OPEN_GAP@": f"{PROTOCOL['rig']['open_gap_m']:.6f}",
        "@CLOSED_GAP@": f"{PROTOCOL['rig']['closed_gap_m']:.6f}",
        "@SETTLE_S@": str(PROTOCOL["phases_s"]["settle"]),
        "@CLOSE_S@": str(PROTOCOL["phases_s"]["close"]),
        "@LIFT_S@": str(spec["lift_s"]),
        "@HOLD_S@": str(PROTOCOL["phases_s"]["hold"]),
        "@LIFT_HEIGHT@": str(PROTOCOL["rig"]["lift_height_m"]),
        "@KP_FINGER@": str(PROTOCOL["control"]["kp_finger"]),
        "@KD_FINGER@": str(PROTOCOL["control"]["kd_finger"]),
        "@MAX_FINGER_FORCE@": str(PROTOCOL["control"]["max_finger_force_n"]),
        "@KP_LIFT@": str(PROTOCOL["control"]["kp_lift"]),
        "@KD_LIFT@": str(PROTOCOL["control"]["kd_lift"]),
        "@MAX_LIFT_FORCE@": str(PROTOCOL["control"]["max_lift_force_n"]),
        "@GRIPPER_MASS@": "0.6",
    }
    for token, replacement in values.items():
        text = text.replace(token, replacement)
    leftover = [token for token in values if token in text]
    if "@" in text.replace("<!--", ""):
        pass
    if leftover:
        raise SystemExit(f"unrendered tokens: {leftover}")
    return text


def loaded_native_libraries(pid: int) -> dict[str, str]:
    """Identity of the physics engine that is actually mapped, not the flag we asked for."""
    paths: set[str] = set()
    try:
        for line in Path(f"/proc/{pid}/maps").read_text().splitlines():
            parts = line.split(maxsplit=5)
            if len(parts) < 6:
                continue
            path = parts[5]
            if path.startswith("/") and ("dartsim" in path or "gz-sim8" in path or "gz-sim-" in path):
                paths.add(path)
    except OSError:
        return {}
    return {path: sha256(Path(path)) for path in sorted(paths) if Path(path).is_file()}


def run_trial(spec: dict, run_dir: Path, steps_total: int, timeout_s: float) -> dict:
    cell = run_dir / spec["trial"]
    cell.mkdir(parents=True, exist_ok=False)
    world = cell / "world.sdf"
    log = cell / "steps.jsonl"
    world.write_text(render_world(spec, log.resolve()))

    env = dict(os.environ)
    env["GZ_SIM_SYSTEM_PLUGIN_PATH"] = str(PLUGIN.parent)
    env["GZ_PARTITION"] = "grasp-probe-" + uuid.uuid4().hex[:12]
    env.pop("GZ_SIM_RESOURCE_PATH", None)
    argv = ["gz", "sim", "-s", "-r", "--iterations", str(steps_total), str(world)]
    started = time.time()
    result = dict(spec)
    result.update(world_sha256=sha256(world), command=argv, plugin_sha256=sha256(PLUGIN))
    with (cell / "sim.log").open("w") as stream:
        proc = subprocess.Popen(argv, stdout=stream, stderr=subprocess.STDOUT,
                                env=env, start_new_session=True)
        time.sleep(0.5)  # let the loader map the physics engine before sampling
        libraries = loaded_native_libraries(proc.pid)
        result["engine_libraries"] = libraries
        result["dartsim_loaded"] = any("dartsim" in path for path in libraries)
        try:
            code = proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGINT)
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            code = "timeout"
    result.update(exit_code=code, wall_s=round(time.time() - started, 3),
                  steps_bytes=log.stat().st_size if log.exists() else 0)
    if log.exists():
        result["steps_sha256"] = sha256(log)
    (cell / "meta.json").write_text(json.dumps(result, indent=2, sort_keys=True) + chr(10))
    return result


def gz_version() -> str:
    try:
        return subprocess.run(["gz", "sim", "--version"], capture_output=True, text=True,
                              timeout=60).stdout.splitlines()[0].strip()
    except (OSError, subprocess.SubprocessError, IndexError):
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["acceptance", "stress", "smoke", "magnet"], default="acceptance")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--only", type=int, help="run a single trial index (1-based)")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--timeout-s", type=float, default=180.0)
    args = parser.parse_args()

    build_plugin(args.rebuild)
    if not PLUGIN.exists():
        raise SystemExit(f"plugin not built: {PLUGIN}")

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    run_dir = args.out or (ROOT / "results" / f"{args.stage}-{stamp}")
    run_dir.mkdir(parents=True, exist_ok=False)

    specs = trial_specs(args.stage)
    if args.only:
        specs = [specs[args.only - 1]]
    steps_total = int(round(sum(PROTOCOL["phases_s"].values()) / PROTOCOL["physics"]["step_s"])) + 1

    protocol = dict(PROTOCOL)
    protocol.update(stage=args.stage, run_id=run_dir.name, gz_version=gz_version(),
                    steps_per_trial=steps_total, trials=[spec["trial"] for spec in specs],
                    mode="magnet" if args.stage == "magnet" else "contact")
    if args.stage == "magnet":
        protocol["magnet_ladder_kg"] = list(MAGNET_LADDER_KG)
        protocol["carrier"] = "gz::sim::systems::DetachableJoint (rigid joint, no contact)"
    (run_dir / "protocol.json").write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")

    failures = []
    for index, spec in enumerate(specs, start=1):
        print(f"[{index}/{len(specs)}] {spec['trial']} ...", flush=True)
        try:
            meta = run_trial(spec, run_dir, steps_total, args.timeout_s)
        except Exception as exc:  # noqa: BLE001 - a broken trial must not hide the others
            failures.append(spec["trial"])
            print(f"    FAILED: {exc!r}", flush=True)
            continue
        print(f"    exit={meta['exit_code']} bytes={meta['steps_bytes']} wall={meta['wall_s']}s",
              flush=True)
        if meta["exit_code"] != 0 or meta["steps_bytes"] == 0:
            failures.append(spec["trial"])

    print(f"run_dir={run_dir}")
    print(f"trials={len(specs)} broken={len(failures)} {failures}")
    return 0 if not failures else 2


if __name__ == "__main__":
    sys.exit(main())
