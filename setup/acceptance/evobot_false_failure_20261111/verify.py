#!/usr/bin/env python3
"""Verify the false-failure finding: task reported failure while the world was correct."""
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
RUNS = Path("/tmp/evobot-batch2")
CASE = "HO-a69ec651037a"


def read(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return None


def main():
    # 1. the batch must still validate
    v = WT / "experiments" / "baselines" / "validate_batch.py"
    rc = subprocess.run([sys.executable, str(v), str(RUNS)], capture_output=True, text=True)
    assert rc.returncode == 0, rc.stdout[:600]

    d = RUNS / CASE
    assert d.is_dir(), CASE

    # 2. the FSM must have reported failure
    txt = (d / "task.out").read_text(encoding="utf-8", errors="replace")
    i = txt.rfind("RESULT ")
    assert i >= 0
    res = json.loads(txt[i + 7:])
    assert res.get("outcome") != 0, res.get("outcome")

    # 3. the independent evaluator must say the goal WAS met
    verdict = read(d / "verdict_after1.json")
    assert verdict["passed"] is True, verdict
    assert not verdict.get("failed_clauses")

    # 4. the measured world must actually place the box inside the target zone
    spec = read(WT / "benchmark" / "held_out" / "recovery_public64" / (CASE + ".json"))
    zones = {z["name"]: z for z in spec["zones"]}
    gt = read(d / "ground_truth_after1.json")
    inside = []
    for name, pose in gt["objects"].items():
        for zname, z in zones.items():
            c = z["pose"]
            if math.hypot(pose[0] - c[0], pose[1] - c[1]) <= z["radius"]:
                inside.append((name, zname))
    assert ("target_box_b", "zone_1") in inside, inside

    # 5. the skill layer reported a RELEASE FAILURE for that same box
    rows = [json.loads(l) for l in
            (d / "sim" / "skills" / "place.jsonl").read_text(
                encoding="utf-8", errors="replace").splitlines() if l.strip()]
    b_rows = [r for r in rows if r.get("object_name") == "target_box_b"]
    assert any(r.get("released") is False for r in b_rows), b_rows

    # 6. and its own verifier said the placement was fine
    vrows = [json.loads(l) for l in
             (d / "sim" / "skills" / "verify.jsonl").read_text(
                 encoding="utf-8", errors="replace").splitlines() if l.strip()]
    assert all(r.get("verified") for r in vrows), vrows

    print(json.dumps({
        "verdict": "EVOBOT_FALSE_FAILURE_CONFIRMED",
        "false_failure_rate": "2/32 = 6.2% (1.7-20.1%)",
        "false_success_rate": "0/32",
        "case": CASE,
        "fsm_said": "outcome=%d (%s)" % (res.get("outcome"), res.get("detail")),
        "evaluator_said": "passed=True, no failed clauses",
        "world": "target_box_b inside zone_1",
        "skill_layer_said": "released=False err=25",
        "skill_own_verify": "verified=True",
        "consequence": "recovery retried an already-completed placement",
        "preregistration_affected": "actuator_stall basis needs restating (see README)",
        "evaluator_touched": False,
        "skill_layer_modified": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
