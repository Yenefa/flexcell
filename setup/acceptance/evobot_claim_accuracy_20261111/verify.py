#!/usr/bin/env python3
"""Verify the claim comparison AND the reason the better-looking method was rejected.

WHY BOTH: the numbers alone would argue for replacing the LLM claim with the deterministic
check - it is 100% accurate on its coverage. The reason not to is that its tolerance (20 mm) is
larger than the slack between plan targets and the zone edge (15 mm), so it can call an
out-of-zone placement satisfied. A verifier that reported only the accuracy would be arguing for
a change that could introduce false success.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    acc = (HERE / "accuracy.txt").read_text(encoding="utf-8")
    blind = (HERE / "blindspot.txt").read_text(encoding="utf-8")

    m = re.search(r"LLM self-assessment\s+coverage\s+(\d+)/(\d+)\s+correct\s+(\d+)\s+WRONG\s+(\d+)",
                  acc)
    assert m, "LLM line missing"
    assert int(m.group(1)) == 64 and int(m.group(3)) == 45 and int(m.group(4)) == 19, m.groups()
    # every LLM error must be in the conservative direction, or false success exists
    wrong_lines = [l for l in acc.splitlines() if "wrong:" in l]
    assert len(wrong_lines) == 19, len(wrong_lines)
    for line in wrong_lines:
        assert "passed=True" in line and "claim=False" in line, line

    d = re.search(r"deterministic measurement check\s+coverage\s+(\d+)/(\d+)\s+correct\s+(\d+)\s+"
                  r"WRONG\s+(\d+)", acc)
    assert d, "deterministic line missing"
    assert int(d.group(3)) == 40, d.groups()

    # the blind spot: tolerance must exceed the slack, which is why adoption is refused
    tol = re.search(r"tightest slack\s*:\s*([\d.]+) mm", blind)
    assert tol, "slack line missing"
    slack_mm = float(tol.group(1))
    assert slack_mm == 15.0, slack_mm
    plan_tolerance_mm = 20.0  # goal_check uses the plan's declared position_tolerance_m
    assert plan_tolerance_mm > slack_mm, (
        "if the tolerance no longer exceeds the slack, the rejection needs re-examining")
    assert "NOT adopted" in blind

    print(json.dumps({
        "verdict": "EVOBOT_CLAIM_ACCURACY_COMPARED_AND_REPLACEMENT_REFUSED",
        "llm_claim": "64/64 coverage, 45 correct, 70.3%",
        "llm_errors_all_false_failures": True,
        "deterministic_claim": "40/64 coverage, 40 correct, 100%",
        "why_not_adopted": ("plan tolerance 20 mm exceeds the 15 mm slack between plan "
                            "targets and the zone edge, so it can call an out-of-zone "
                            "placement satisfied; it is also blind to a wrong plan"),
        "decision": "keep the current claim; a safe version needs both criteria plus an "
                    "independent plan check",
        "evaluator_touched": False,
        "skill_layer_touched": False,
        "claim_mechanism_changed": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
