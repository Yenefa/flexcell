#!/usr/bin/env python3
"""Verify the replication finding: every observed failure was non-reproducible."""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
text = (HERE / "replication.txt").read_text(encoding="utf-8")


def main():
    def grab(p):
        m = re.search(p, text)
        assert m, p
        return int(m.group(1))

    n = grab(r"instances with 2\+ replicates : (\d+)")
    stable_pass = grab(r"STABLE PASS\s*:\s*(\d+)")
    stable_fail = grab(r"STABLE FAIL\s*:\s*(\d+)")
    mixed = grab(r"MIXED \(outcome flipped\)\s*:\s*(\d+)")

    assert n == 32, n
    assert stable_pass + stable_fail + mixed == n
    # the whole point: no instance failed in both replicates
    assert stable_fail == 0, ("a stable failure now exists, so the claim must be rewritten",
                              stable_fail)
    assert mixed == 8, mixed
    assert stable_pass == 24, stable_pass

    # each flip must be visible in the per-instance table as pass/FAIL on the same row
    flip_rows = [l for l in text.splitlines()
                 if "MIXED" in l and "pass" in l and "FAIL" in l]
    assert len(flip_rows) >= mixed, len(flip_rows)

    print(json.dumps({
        "verdict": "EVOBOT_FAILURES_NOT_REPRODUCIBLE",
        "instances_with_two_replicates": n,
        "stable_pass": stable_pass,
        "stable_fail": stable_fail,
        "flipped": mixed,
        "flip_rate": "25.0%",
        "what_changes": ("failure counts describe RUNS, not instances; single-batch A/B "
                         "cannot separate an effect from this noise"),
        "what_survives": ("mechanism evidence - whether a step ran, whether a decision was "
                          "recorded - and goal_check 2->0, which rests on the mechanism"),
        "what_does_not_survive": "the goal_check claim of gains 0->2",
        "evaluator_touched": False,
        "skill_layer_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
