#!/usr/bin/env python3
"""Synthetic-fixture tests for analyze.py.

Two entry points, no third-party dependency and no Gazebo:

    python3 research/grasp_contact_probe/scripts/test_analyze.py
    python3 -m pytest research/grasp_contact_probe/scripts/test_analyze.py

Fixtures mirror the real run_probe.py output (acceptance block, object_specs,
box_a-01 style directories, cmd.* commanded effort, contacts.*_pad_force,
per-trial meta.json with hashes and exit code) and are written into a fresh
temporary directory. Nothing here reads a real run or starts a simulator.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import math
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze  # noqa: E402

STEP_S = 0.001
SETTLE_S, CLOSE_S, LIFT_S, HOLD_S = 0.30, 0.40, 0.50, 0.50
TOTAL_S = SETTLE_S + CLOSE_S + LIFT_S + HOLD_S
STEPS = int(round(TOTAL_S / STEP_S)) + 1
LIFT_HEIGHT_M = 0.15
REL_Z_M = 0.02
PAD_FORCE_N = 2.04
FINGER_CMD_N = 7.5
JITTER = (
    {"x": 0.0000, "y": 0.0000, "yaw_deg": 0.0},
    {"x": 0.0015, "y": 0.0000, "yaw_deg": 1.5},
    {"x": -0.0015, "y": 0.0008, "yaw_deg": -1.5},
    {"x": 0.0008, "y": -0.0012, "yaw_deg": 2.0},
    {"x": -0.0008, "y": 0.0012, "yaw_deg": -2.0},
)
OBJECTS = (
    ("box_a", {"size_m": 0.035, "mass_kg": 0.05, "mu": 1.0}),
    ("box_b", {"size_m": 0.050, "mass_kg": 0.12, "mu": 1.0}),
)
STRESS_SPECS = (
    {"trial": "stress-load-0.50kg", "mass_kg": 0.50, "mu": 1.0, "size_m": 0.035, "slip_mm": 0.0},
    {"trial": "stress-load-1.00kg", "mass_kg": 1.00, "mu": 1.0, "size_m": 0.035, "slip_mm": 0.0},
    {"trial": "stress-load-1.20kg", "mass_kg": 1.20, "mu": 1.0, "size_m": 0.035, "slip_mm": 8.85},
    {"trial": "stress-load-1.50kg", "mass_kg": 1.50, "mu": 1.0, "size_m": 0.035, "slip_mm": 150.0},
)


# --------------------------------------------------------------------------- #
# Fixture construction.
# --------------------------------------------------------------------------- #
def phase_of(t: float) -> str:
    if t < SETTLE_S:
        return "settle"
    if t < SETTLE_S + CLOSE_S:
        return "close"
    if t < SETTLE_S + CLOSE_S + LIFT_S:
        return "lift"
    return "hold"


def lift_target(t: float) -> float:
    start = SETTLE_S + CLOSE_S
    if t <= start:
        return 0.0
    u = min(1.0, (t - start) / LIFT_S)
    return LIFT_HEIGHT_M * (u * u * (3.0 - 2.0 * u))


def set_rel(sample: dict, position) -> None:
    """Set rel.p and keep obj consistent with base (identity base rotation)."""
    sample["rel"]["p"] = list(position)
    base = sample["base"]["p"]
    sample["obj"]["p"] = [base[axis] + position[axis] for axis in range(3)]


def set_rel_yaw(sample: dict, yaw_deg: float) -> None:
    half = math.radians(yaw_deg) / 2.0
    quaternion = [0.0, 0.0, math.sin(half), math.cos(half)]
    sample["rel"]["q"] = list(quaternion)
    sample["obj"]["q"] = list(quaternion)


def sample_at(index: int) -> dict:
    t = index * STEP_S
    z = lift_target(t)
    phase = phase_of(t)
    if phase == "settle":
        left_pad = right_pad = 0
        pad_force = 0.0
        ground = 1
        obj_contacts = 1
        finger_cmd = 0.0
    elif phase == "close":
        left_pad = right_pad = 1
        pad_force = PAD_FORCE_N
        ground = 1
        obj_contacts = 3
        finger_cmd = FINGER_CMD_N
    else:
        left_pad = right_pad = 1
        pad_force = PAD_FORCE_N
        ground = 0
        obj_contacts = 2
        finger_cmd = FINGER_CMD_N
    return {
        "iter": index,
        "t": t,
        "phase": phase,
        "obj": {"p": [0.0, 0.0, z + REL_Z_M], "q": [0.0, 0.0, 0.0, 1.0]},
        "base": {"p": [0.0, 0.0, z], "q": [0.0, 0.0, 0.0, 1.0]},
        "rel": {"p": [0.0, 0.0, REL_Z_M], "q": [0.0, 0.0, 0.0, 1.0]},
        "joints": {
            "left": {"q": 0.0, "qd": 0.0, "f": 0.0},
            "right": {"q": 0.0, "qd": 0.0, "f": 0.0},
            "lift": {"q": z, "qd": 0.0, "f": 0.0},
        },
        "contacts": {
            "left_pad": left_pad,
            "right_pad": right_pad,
            "left_pad_force": pad_force,
            "right_pad_force": pad_force,
            "obj_contacts": obj_contacts,
            "obj_ground": ground,
        },
        "cmd": {"left": -finger_cmd, "right": finger_cmd, "lift": 6.37 + z * 6.5},
        "gap_target": 0.056 if phase == "settle" else 0.02,
        "lift_target": z,
    }


def merge(base: dict, patch: dict) -> dict:
    result = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = value
    return result


def trial_names(trials_per_object) -> list[str]:
    names: list[str] = []
    for (name, _), count in zip(OBJECTS, trials_per_object):
        names.extend("%s-%02d" % (name, index + 1) for index in range(count))
    return names


def protocol_document(trials_per_object=(5, 5), protocol_trials=None) -> dict:
    declared = trial_names(protocol_trials or trials_per_object)
    return {
        "schema_version": 1,
        "kind": "GRASP_CONTACT_PROBE",
        "question": "Can a parallel jaw hold and lift a rigid box with contact friction alone?",
        "physics": {"engine": "gz-sim 8 dartsim", "step_s": STEP_S},
        "rig": {"open_gap_m": 0.056, "closed_gap_m": 0.020, "lift_height_m": LIFT_HEIGHT_M},
        "phases_s": {"settle": SETTLE_S, "close": CLOSE_S, "lift": LIFT_S, "hold": HOLD_S},
        "control": {
            "finger_servo": "Force = clamp(kp*(q_target-q) - kd*qd, +/-max_force)",
            "kp_finger": 1000.0,
            "kd_finger": 20.0,
            "max_finger_force_n": 20.0,
            "kp_lift": 4000.0,
            "kd_lift": 80.0,
            "max_lift_force_n": 80.0,
        },
        "controls": {
            "load_ladder_kg": [0.5, 1.0, 1.2, 1.5],
            "load_ladder_prediction": "slip above m = 2*mu*N/(g+a) = 15.0/13.4 = 1.12 kg",
            "slip_expected": {"mass_kg": 0.5, "mu": 0.2,
                              "why": "2*mu*N = 2*0.2*7.5 = 3.0 N < m*(g+a) = 6.7 N"},
        },
        "object_specs": {name: dict(spec) for name, spec in OBJECTS},
        "acceptance": {
            "reference": "mean rel pose over the last 50 ms of the close phase",
            "drift_translation_mm_max": 2.0,
            "drift_rotation_deg_max": 5.0,
            "drop_relative_z_mm": -20.0,
            "drop_abs_drift_mm": 30.0,
            "trials_required_pass": sum(trials_per_object),
            "objects": [name for name, _ in OBJECTS],
        },
        "trials_per_object": 5,
        "trials": declared,
        "stage": "acceptance",
        "run_id": "synthetic",
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_trial(root: Path, name: str, object_name: str, mass: float, mu: float,
                 size: float, mutate=None, steps: int = STEPS) -> None:
    directory = root / name
    directory.mkdir()
    world = directory / "world.sdf"
    world.write_text("<sdf version='1.10'><!-- synthetic fixture world --></sdf>\n",
                     encoding="utf-8")
    samples = [sample_at(index) for index in range(steps)]
    if mutate is not None:
        for index, sample in enumerate(samples):
            mutate(name, index, sample["t"], sample)
    steps_path = directory / "steps.jsonl"
    with steps_path.open("w", encoding="utf-8", newline="\n") as stream:
        for sample in samples:
            stream.write(json.dumps(sample) + "\n")
    index = int(name.rsplit("-", 1)[1]) - 1 if name.rsplit("-", 1)[1].isdigit() else 0
    meta = {
        "trial": name,
        "group": "acceptance",
        "object_name": object_name,
        "size_m": size,
        "mass_kg": mass,
        "mu": mu,
        "jitter": JITTER[index % len(JITTER)],
        "lift_s": LIFT_S,
        "exit_code": 0,
        "steps_bytes": steps_path.stat().st_size,
        "steps_sha256": _sha256(steps_path),
        "world_sha256": _sha256(world),
    }
    (directory / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def make_run(root: Path, trials_per_object=(5, 5), protocol_trials=None, mutate=None,
             protocol_patch=None, steps: int = STEPS) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    document = protocol_document(trials_per_object, protocol_trials)
    if protocol_patch:
        document = merge(document, protocol_patch)
    (root / "protocol.json").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    for name in trial_names(trials_per_object):
        object_name = name.rsplit("-", 1)[0]
        spec = dict(OBJECTS)[object_name]
        _write_trial(root, name, object_name, spec["mass_kg"], spec["mu"], spec["size_m"],
                     mutate=mutate, steps=steps)
    return root


def make_stress_run(root: Path, specs=STRESS_SPECS) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    document = protocol_document((5, 5))
    document["stage"] = "stress"
    document["run_id"] = "synthetic-stress"
    document["trials"] = [spec["trial"] for spec in specs]
    (root / "protocol.json").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    for spec in specs:
        def slip(name: str, index: int, t: float, sample: dict) -> None:
            start = SETTLE_S + CLOSE_S
            if spec["slip_mm"] and t > start:
                u = min(1.0, (t - start) / LIFT_S)
                set_rel(sample, (0.0, 0.0, REL_Z_M - spec["slip_mm"] / 1000.0 * u))
        _write_trial(root, spec["trial"], "box_a", spec["mass_kg"], spec["mu"],
                     spec["size_m"], mutate=slip)
    return root


@contextlib.contextmanager
def temporary_run(factory=make_run, **kwargs):
    root = Path(tempfile.mkdtemp(prefix="grasp-probe-test-"))
    try:
        factory(root, **kwargs)
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def run_cli(root: Path, *extra: str):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = analyze.main(["--run-dir", str(root), *extra])
    return code, out.getvalue(), err.getvalue()


def read_summary(root: Path) -> dict:
    return json.loads((root / "analysis" / "summary.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Fixture mutations.
# --------------------------------------------------------------------------- #
def drift_25_mm(name: str, index: int, t: float, sample: dict) -> None:
    if name == "box_a-03" and t > SETTLE_S + CLOSE_S:
        set_rel(sample, (0.0025, 0.0, REL_Z_M))


def drop_25_mm(name: str, index: int, t: float, sample: dict) -> None:
    start = SETTLE_S + CLOSE_S
    if name == "box_b-01" and t > start:
        u = min(1.0, (t - start) / LIFT_S)
        set_rel(sample, (0.0, 0.0, REL_Z_M - 0.025 * u))


def norm_drop_35_mm(name: str, index: int, t: float, sample: dict) -> None:
    if name == "box_a-02" and t > SETTLE_S + CLOSE_S:
        set_rel(sample, (0.035, 0.0, REL_Z_M))


def ground_stuck(name: str, index: int, t: float, sample: dict) -> None:
    if name == "box_a-01":
        sample["contacts"]["obj_ground"] = 1


# --------------------------------------------------------------------------- #
# Tests.
# --------------------------------------------------------------------------- #
def test_perfect_run_passes() -> None:
    with temporary_run() as root:
        code, out, err = run_cli(root)
        assert code == 0, (code, out, err)
        summary = read_summary(root)
        assert summary["verdict"] == "PASS"
        assert summary["mode"] == "acceptance"
        assert summary["passed_trials"] == 10
        assert summary["failed_trials"] == []
        first = summary["trials"][0]
        assert first["samples"] == STEPS
        assert abs(first["drift"]["translation_mm"]) < 1e-6
        assert first["drop"]["drop"] is False
        assert 48 <= first["ref"]["samples"] <= 52
        assert first["meta"]["identity_source"] == "protocol_and_meta"
        assert first["contacts"]["obj_ground_evidence"] == "lost_after_lift"
        assert abs(first["contacts"]["obj_ground_lost_t"] - (SETTLE_S + CLOSE_S)) < 0.002
        assert first["forces"]["commanded"]["close"]["max_abs_n"] == FINGER_CMD_N
        measured = first["forces"]["measured_contact"]["per_phase"]["lift"]
        assert abs(measured["per_pad_peak_max_n"] - PAD_FORCE_N) < 1e-9
        assert first["forces"]["normal_force_applied_per_pad_n"] == FINGER_CMD_N
        report = (root / "analysis" / "REPORT.md").read_text(encoding="utf-8")
        assert "本结果不能证明什么" in report
        assert "DART" in report
        assert "PASS" in report
        assert "指令力" in report and "实测接触力" in report
        assert summary["limitations"][0].startswith("仅两种尺寸")


def test_acceptance_friction_check_cannot_decide() -> None:
    with temporary_run() as root:
        code, out, err = run_cli(root)
        assert code == 0, (code, out, err)
        friction = read_summary(root)["friction_cone_check"]
        assert friction["status"] == "无法判定"
        assert friction["trial_count"] == 10
        assert friction["declared_predicted_slip_mass_kg"] == 1.12


def test_drift_above_threshold_fails() -> None:
    with temporary_run(mutate=drift_25_mm) as root:
        code, out, err = run_cli(root)
        assert code == 1, (code, out, err)
        summary = read_summary(root)
        assert summary["verdict"] == "FAIL"
        assert summary["failed_trials"] == ["box_a-03"]
        failed = summary["trials"][2]
        assert abs(failed["drift"]["translation_mm"] - 2.5) < 1e-6
        assert failed["failure_modes"] == ["slip"]
        assert failed["observed_slip"] is True


def test_thresholds_come_from_protocol() -> None:
    with temporary_run(mutate=drift_25_mm,
                       protocol_patch={"acceptance": {"drift_translation_mm_max": 3.0}}) as root:
        code, out, err = run_cli(root)
        assert code == 0, (code, out, err)
        summary = read_summary(root)
        assert summary["verdict"] == "PASS"
        assert summary["criteria"]["drift_translation_max_mm"] == 3.0


def test_drop_z_criterion_detected() -> None:
    with temporary_run(mutate=drop_25_mm) as root:
        code, out, err = run_cli(root)
        assert code == 1, (code, out, err)
        summary = read_summary(root)
        trial = summary["trials"][5]
        assert trial["drop"]["drop"] is True
        assert trial["drop"]["base_z_triggered"] is True
        assert trial["drop"]["base_z_trigger_t"] is not None
        assert abs(trial["drop"]["base_z_decline_mm"] - 25.0) < 1e-6
        assert trial["drop"]["rel_norm_triggered"] is False
        assert trial["failure_modes"][0] == "drop"
        assert summary["failure_modes"] == {"drop": ["box_b-01"]}


def test_drop_norm_criterion_detected() -> None:
    with temporary_run(mutate=norm_drop_35_mm) as root:
        code, out, err = run_cli(root)
        assert code == 1, (code, out, err)
        trial = read_summary(root)["trials"][1]
        assert trial["drop"]["drop"] is True
        assert trial["drop"]["rel_norm_triggered"] is True
        assert trial["drop"]["base_z_triggered"] is False


def test_ground_evidence_inconsistency_rejected() -> None:
    with temporary_run(mutate=ground_stuck) as root:
        code, out, err = run_cli(root)
        assert code == 2, (code, out, err)
        assert "contradict" in err


def test_rotation_criterion_when_declared() -> None:
    def yaw(name: str, index: int, t: float, sample: dict) -> None:
        if name == "box_a-05" and t > SETTLE_S + CLOSE_S:
            set_rel_yaw(sample, 0.5)

    with temporary_run(mutate=yaw,
                       protocol_patch={"acceptance": {"drift_rotation_deg_max": 0.01}}) as root:
        code, out, err = run_cli(root)
        assert code == 1, (code, out, err)
        trial = read_summary(root)["trials"][4]
        assert trial["drift"]["rotation_deg"] > 0.4
        assert trial["drift"]["rotation_within_limit"] is False


def test_jitter_classified() -> None:
    def jitter(name: str, index: int, t: float, sample: dict) -> None:
        if name == "box_b-03" and t > SETTLE_S + CLOSE_S:
            offset = 0.0005 if index % 2 else -0.0005
            set_rel(sample, (0.0025, 0.0, REL_Z_M + offset))

    with temporary_run(mutate=jitter) as root:
        code, out, err = run_cli(root)
        assert code == 1, (code, out, err)
        summary = read_summary(root)
        trial = summary["trials"][7]
        assert trial["pass"] is False
        assert "jitter" in trial["failure_modes"]
        assert "jitter" in summary["failure_modes"]


def test_nonfinite_value_rejected() -> None:
    def poison(name: str, index: int, t: float, sample: dict) -> None:
        if name == "box_a-02" and index == 400:
            sample["rel"]["p"][2] = float("nan")

    with temporary_run(mutate=poison) as root:
        code, out, err = run_cli(root)
        assert code == 2, (code, out, err)
        assert "non-finite" in err
        assert not (root / "analysis").exists()


def test_out_of_order_timestamps_rejected() -> None:
    root = Path(tempfile.mkdtemp(prefix="grasp-probe-test-"))
    try:
        make_run(root)
        steps_path = root / "box_a-02" / "steps.jsonl"
        samples = [json.loads(line) for line in steps_path.read_text(encoding="utf-8").splitlines()]
        samples[600]["t"], samples[601]["t"] = samples[601]["t"], samples[600]["t"]
        with steps_path.open("w", encoding="utf-8", newline="\n") as stream:
            for sample in samples:
                stream.write(json.dumps(sample) + "\n")
        code, out, err = run_cli(root)
        assert code == 2, (code, out, err)
        assert "not strictly increasing" in err
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_duplicate_iter_rejected() -> None:
    def duplicate(name: str, index: int, t: float, sample: dict) -> None:
        if name == "box_a-01" and index == 500:
            sample["iter"] = 499

    with temporary_run(mutate=duplicate) as root:
        code, out, err = run_cli(root)
        assert code == 2, (code, out, err)
        assert "does not increase" in err


def test_contact_sentinel_rejected() -> None:
    def sentinel(name: str, index: int, t: float, sample: dict) -> None:
        if name == "box_a-03" and index == 500:
            sample["contacts"]["left_pad"] = -1

    with temporary_run(mutate=sentinel) as root:
        code, out, err = run_cli(root)
        assert code == 2, (code, out, err)
        assert "unknown" in err
        assert "infer zero" in err


def test_world_frame_rel_rejected() -> None:
    def world_rel(name: str, index: int, t: float, sample: dict) -> None:
        if name == "box_a-04" and index == 900:
            sample["rel"]["p"] = list(sample["obj"]["p"])

    with temporary_run(mutate=world_rel) as root:
        code, out, err = run_cli(root)
        assert code == 2, (code, out, err)
        assert "base frame" in err


def test_empty_run_dir_rejected() -> None:
    root = Path(tempfile.mkdtemp(prefix="grasp-probe-test-"))
    try:
        code, out, err = run_cli(root)
        assert code == 2, (code, out, err)
        assert "missing protocol.json" in err
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_missing_meta_rejected() -> None:
    with temporary_run() as root:
        (root / "box_a-03" / "meta.json").unlink()
        code, out, err = run_cli(root)
        assert code == 2, (code, out, err)
        assert "missing meta.json" in err


def test_trial_numbering_gap_rejected_in_scan_mode() -> None:
    with temporary_run(protocol_patch={"trials": None}) as root:
        (root / "box_a-03").rename(root / "box_a-99")
        code, out, err = run_cli(root)
        assert code == 2, (code, out, err)
        assert "gaps" in err


def test_missing_declared_trial_dir_rejected() -> None:
    with temporary_run() as root:
        shutil.rmtree(root / "box_b-05")
        code, out, err = run_cli(root)
        assert code == 2, (code, out, err)
        assert "missing" in err
        assert "box_b-05" in err


def test_extra_trial_dir_rejected() -> None:
    with temporary_run() as root:
        (root / "junk-01").mkdir()
        code, out, err = run_cli(root)
        assert code == 2, (code, out, err)
        assert "not in the preregistered trial list" in err


def test_object_specs_cross_checked() -> None:
    with temporary_run(protocol_patch={
        "object_specs": {"box_b": {"size_m": 0.050, "mass_kg": 0.12, "mu": 0.7}}}) as root:
        code, out, err = run_cli(root)
        assert code == 2, (code, out, err)
        assert "differs from the preregistered" in err


def test_ref_window_deviation_rejected() -> None:
    with temporary_run(protocol_patch={"ref_window_s": 0.10}) as root:
        code, out, err = run_cli(root)
        assert code == 2, (code, out, err)
        assert "preregistered" in err


def test_reference_text_deviation_rejected() -> None:
    with temporary_run(protocol_patch={"acceptance": {
            "reference": "mean rel pose over the last 30 ms of the close phase"}}) as root:
        code, out, err = run_cli(root)
        assert code == 2, (code, out, err)
        assert "30 ms" in err


def test_exploratory_stage_stress() -> None:
    with temporary_run(factory=make_stress_run) as root:
        code, out, err = run_cli(root, "--stage", "stress")
        assert code == 0, (code, out, err)
        summary = read_summary(root)
        assert summary["verdict"] == "EXPLORATORY"
        assert summary["mode"] == "exploratory"
        assert summary["passed_trials"] is None
        assert summary["failed_trials"] == []
        assert all(trial["pass"] is None for trial in summary["trials"])
        friction = summary["friction_cone_check"]
        assert friction["status"] == "符合", friction
        assert friction["agreement_count"] == 4
        assert friction["predicted_slip_mass_kg"] == 1.12
        assert friction["observed_boundary_kg"] == {"held_max_kg": 1.0, "slip_min_kg": 1.2}
        report = (root / "analysis" / "REPORT.md").read_text(encoding="utf-8")
        assert "探索分析报告" in report
        assert "friction_cone_check" in report
        assert "符合" in report


def test_exploratory_stage_mismatch_rejected() -> None:
    with temporary_run(factory=make_stress_run) as root:
        code, out, err = run_cli(root, "--stage", "smoke")
        assert code == 2, (code, out, err)
        assert "does not match" in err


def test_stress_run_rejected_without_exploratory_flag() -> None:
    with temporary_run(factory=make_stress_run) as root:
        code, out, err = run_cli(root)
        assert code == 2, (code, out, err)
        assert "exploratory" in err


def test_acceptance_run_rejected_in_exploratory_mode() -> None:
    with temporary_run() as root:
        code, out, err = run_cli(root, "--exploratory")
        assert code == 2, (code, out, err)
        assert "acceptance" in err


def test_reports_are_not_overwritten() -> None:
    with temporary_run() as root:
        code, out, err = run_cli(root)
        assert code == 0, (code, out, err)
        code, out, err = run_cli(root)
        assert code == 2, (code, out, err)
        assert "refusing to overwrite" in err


def test_empty_step_log_rejected() -> None:
    with temporary_run() as root:
        (root / "box_a-01" / "steps.jsonl").write_text("", encoding="utf-8")
        code, out, err = run_cli(root)
        assert code == 2, (code, out, err)
        assert "empty step log" in err


def test_tampered_step_log_rejected() -> None:
    with temporary_run() as root:
        steps_path = root / "box_a-01" / "steps.jsonl"
        with steps_path.open("a", encoding="utf-8", newline="\n") as stream:
            extra = sample_at(0)
            extra["iter"] = 10 ** 6
            extra["t"] = 100.0
            extra["phase"] = "hold"
            stream.write(json.dumps(extra) + "\n")
        code, out, err = run_cli(root)
        assert code == 2, (code, out, err)
        assert "sha256" in err


# --------------------------------------------------------------------------- #
# Plain-python entry point (pytest also collects the functions above).
# --------------------------------------------------------------------------- #
def main() -> int:
    selected = [(name, value) for name, value in sorted(globals().items())
                if name.startswith("test_") and callable(value)]
    failures = 0
    for name, function in selected:
        try:
            function()
        except Exception:  # noqa: BLE001 - a test runner must keep going
            failures += 1
            print("FAIL %s" % name)
            traceback.print_exc()
        else:
            print("ok   %s" % name)
    print("%d passed, %d failed" % (len(selected) - failures, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
