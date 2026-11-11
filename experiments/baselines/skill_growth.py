#!/usr/bin/env python3
"""Drive one arm of the skill-growth task: an open-loop plan, or a closed-loop procedure.

ARM B (baseline, open loop): emit both poses from one observation and dispatch. This is every
plan the runtime has ever produced. It has to guess where the red block will actually land.

ARM C: place the red block, MEASURE it, then place the blue block relative to where it really is,
and refine until the measured offset holds. This procedure did not exist in the runtime before
this task; it is composed only of primitives that already did (single-stage execution plus ground
truth capture).

Neither arm grades itself. The independent evaluator decides afterwards.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp")
sys.path.insert(0, str(ROOT / "runtime" / "skills"))
import adaptive

CLIENT = str(ROOT / "experiments" / "baselines" / "composite_client.py")
GT = str(ROOT / "benchmark" / "evaluators" / "capture_ground_truth.py")

OBJ = ["target_box_a", "target_box_b"]


def observe(d):
    out = Path(d) / "observed.json"
    subprocess.run(["python3", GT, str(out)] + OBJ, check=True,
                   capture_output=True, text=True)
    return json.loads(out.read_text(encoding="utf-8"))["objects"]


def _at(measured, name, pose, tol=0.02):
    if name not in measured:
        return False
    p = measured[name]
    return abs(p[0] - pose[0]) <= tol and abs(p[1] - pose[1]) <= tol


def exec_stage(d, object_name, pose, tag):
    plan = {
        "task_id": "skg-" + tag,
        "initial_objects": [
            {"object_name": "target_box_a", "position": [0.22, 0.0, 0.018]},
            {"object_name": "target_box_b", "position": [0.20, -0.18, 0.018]}],
        "stages": [{"stage_id": tag, "object_name": object_name, "place_pose": pose}],
        "final_empty_positions": [],
        "position_tolerance_m": 0.02,
        "clearance_m": 0.05,
        "motion_profile_id": "demo_slow",
    }
    p = Path(d) / ("plan_%s.json" % tag)
    p.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    out = subprocess.run(["python3", CLIENT, "--plan", str(p), "--timeout", "300"],
                         capture_output=True, text=True)
    (Path(d) / ("stage_%s.out" % tag)).write_text(out.stdout + out.stderr,
                                                  encoding="utf-8")
    # The action self-report is NOT the verdict. It has been measured to say "unconfirmed"
    # while the object is exactly where it was asked to go, so the world is what decides.
    arrived = _at(observe(d), object_name, pose)
    return {"stdout": out.stdout, "arrived_by_measurement": arrived}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["B", "C"], required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    d = Path(a.out)
    d.mkdir(parents=True, exist_ok=True)
    report = {"arm": a.arm}

    if a.arm == "B":
        # one observation, both poses, no looking in between
        plan = {
            "task_id": "skg-B",
            "initial_objects": [
                {"object_name": "target_box_a", "position": [0.22, 0.0, 0.018]},
                {"object_name": "target_box_b", "position": [0.20, -0.18, 0.018]}],
            "stages": [
                {"stage_id": "a-0", "object_name": "target_box_a",
                 "place_pose": [0.12, -0.15, 0.0175],
                 "spread_offset_m": 0.0, "spread_axis": "x"},
                {"stage_id": "b-1", "object_name": "target_box_b",
                 "place_pose": [0.12, -0.09, 0.0175],
                 "spread_offset_m": 0.0, "spread_axis": "x"}],
            "final_empty_positions": [],
            "position_tolerance_m": 0.02, "clearance_m": 0.05,
            "motion_profile_id": "demo_slow",
        }
        p = d / "plan_B.json"
        p.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        out = subprocess.run(["python3", CLIENT, "--plan", str(p), "--timeout", "400"],
                             capture_output=True, text=True)
        (d / "task.out").write_text(out.stdout + out.stderr, encoding="utf-8")
        report["static_intent"] = {"red": [0.12, -0.15], "blue": [0.12, -0.09]}
    else:
        exec_stage(d, "target_box_a", [0.12, -0.15, 0.0175], "a-0")
        log = []
        res = adaptive.place_relative(
            exec_stage=lambda name, pose: exec_stage(d, name, pose, "b-%d" % len(log)),
            observe=lambda: observe(d),
            reference="target_box_a", obj="target_box_b",
            offset=[0.0, 0.06], tolerance_m=0.006, max_refinements=3, log=log)
        report.update(res)
        (d / "skill_log.json").write_text(json.dumps(report, indent=2) + "\n",
                                          encoding="utf-8")
    measured = observe(d)
    (d / "ground_truth.json").write_text(
        json.dumps({"objects": measured}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
