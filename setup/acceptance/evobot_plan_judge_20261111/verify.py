#!/usr/bin/env python3
"""Verify the plan-judge study: a held-out set undid an in-sample perfect score."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent


def main():
    r = json.loads((HERE / "results.json").read_text(encoding="utf-8"))
    a = r["runA_public80_used_to_fix_colours"]
    c = r["runC_public64_never_used"]
    assert a["separation"] == 1.0, a
    assert c["separation"] < 0.8, c
    assert c["separation"] < a["separation"]
    assert "not adopted" in r["decision"]
    print(json.dumps({
        "verdict": "EVOBOT_PLAN_JUDGE_FAILED_HELD_OUT",
        "in_sample_used_for_debugging": "%.3f" % a["separation"],
        "held_out_never_used": "%.3f" % c["separation"],
        "lesson": "a perfect score on a set I had already debugged against meant nothing",
        "decision": r["decision"],
        "evaluator_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
