#!/usr/bin/env python3
"""Verify the B/C negative result on unseen task types.

The claim is NEGATIVE: experience changed nothing. The verifier has to prove that, not
just assert it - so it checks that every paired plan is byte-identical, and that the one
apparent C advantage is execution variance rather than a different plan.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"


def main():
    b_dirs = sorted(RUNS.glob("*_B"))
    assert len(b_dirs) == 6, len(b_dirs)
    identical = 0
    differing = []
    for d in b_dirs:
        oid = d.name.rsplit("_", 1)[0]
        c = RUNS / (oid + "_C")
        assert c.exists(), oid
        pb = (d / "plan.json").read_bytes()
        pc = (c / "plan.json").read_bytes()
        if pb == pc:
            identical += 1
        else:
            differing.append(oid)
    assert identical == 6, differing

    # C really did receive lessons; otherwise the null result would be vacuous
    for d in sorted(RUNS.glob("*_C")):
        obs = json.loads((d / "observation_input.json").read_text(encoding="utf-8"))
        assert len(obs.get("experience") or []) >= 1, d.name
    for d in b_dirs:
        obs = json.loads((d / "observation_input.json").read_text(encoding="utf-8"))
        assert not (obs.get("experience") or []), d.name

    # false success must be zero on both arms
    graded = list(RUNS.glob("*/verdict.json"))
    assert len(graded) == 12, len(graded)
    for v in graded:
        doc = json.loads(v.read_text(encoding="utf-8"))
        assert not doc.get("false_success"), v.parent.name

    # the single differing outcome must be execution, not plan divergence
    b = json.loads((RUNS / "HO-42109d30fa00_B" / "task.out").read_text()
                   .split("RESULT ", 1)[1])
    c = json.loads((RUNS / "HO-42109d30fa00_C" / "task.out").read_text()
                   .split("RESULT ", 1)[1])
    assert b["outcome"] != 0 and c["outcome"] == 0

    print(json.dumps({
        "verdict": "EVOBOT_BC_NULL_RESULT_VERIFIED",
        "pairs": len(b_dirs),
        "byte_identical_plans": identical,
        "lessons_injected_into_C": 6,
        "experience_effect": "none observed",
        "false_success_rate": 0.0,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
