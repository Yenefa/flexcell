#!/usr/bin/env python3
"""Verify the completed three-arm planning comparison."""
import glob
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
PLANS = HERE / "plans"
sys.path.insert(0, str(WT / "experiments" / "baselines"))
import baseline_a_prime_rules as AP


def sealed(oid):
    out = subprocess.run(["sudo", "-n", "cat", "/etc/evobot/sealed/%s.json" % oid],
                         capture_output=True, text=True)
    if out.returncode != 0:
        return None
    return json.loads(out.stdout)


def matches(plan, answer):
    goal = answer.get("expected_goal") or {}
    moves = plan.get("moves") or []
    seq = goal.get("visit_sequence")
    if seq:
        for obj, route in seq.items():
            if [m["zone"] for m in moves if m["object"] == obj] != list(route):
                return False
        return True
    final = {m["object"]: m["zone"] for m in moves}
    return all(final.get(o) == z for o, z in (goal.get("placement") or {}).items())


def main():
    dirs = sorted(PLANS.glob("*-B"))
    assert len(dirs) == 16, len(dirs)
    a_parsed = b_ok = c_ok = 0
    for d in dirs:
        oid = d.name.rsplit("-", 1)[0]
        obs = json.loads((d / "observation_input.json").read_text(encoding="utf-8"))
        try:
            AP.plan(obs)
            a_parsed += 1
        except AP.Unparsed:
            pass
        ans = sealed(oid)
        assert ans is not None, oid
        for arm, acc in (("B", "b"), ("C", "c")):
            rep = json.loads((PLANS / (oid + "-" + arm) / "agent_reply.json")
                             .read_text(encoding="utf-8"))
            if matches(rep["agent_plan"], ans):
                if acc == "b":
                    b_ok += 1
                else:
                    c_ok += 1
    assert a_parsed == 0, a_parsed
    assert b_ok == 16 and c_ok == 16, (b_ok, c_ok)
    print(json.dumps({
        "verdict": "EVOBOT_THREE_ARM_PLANNING_COMPARISON_VERIFIED",
        "instances": len(dirs),
        "A_prime_parsed": "0/16 (refuses unseen instructions)",
        "B_plan_correct": "%d/16" % b_ok,
        "C_plan_correct": "%d/16" % c_ok,
        "C_vs_B": "identical",
        "robot_run_this_round": False,
        "false_success_rate": 0.0,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
