#!/usr/bin/env python3
"""Verify the saturation finding: a deterministic parser matches the LLM on these templates."""
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
text = (HERE / "comparison.txt").read_text(encoding="utf-8")


def main():
    def grab(pattern):
        m = re.search(pattern, text)
        assert m, pattern
        return int(m.group(1))

    n = grab(r"instances compared\s*:\s*(\d+)")
    agree = grab(r"rule plan == LLM plan\s*:\s*(\d+)")
    rule_ok = grab(r"rule planner correct\s*:\s*(\d+)")
    llm_ok = grab(r"LLM planner correct\s*:\s*(\d+)")

    assert n == 64, n
    assert rule_ok == 64, ("the deterministic parser no longer saturates", rule_ok)
    assert llm_ok == 64, llm_ok
    assert agree >= 60, agree

    # The parser must not read the answer. Check for ACTUAL LOOKUPS ("key" in quotes),
    # not for the bare word: the module docstring legitimately says it never reads
    # expected_goal, and a naive substring test flagged its own documentation.
    src = (WT / "runtime" / "planner" / "rule_planner.py").read_text(encoding="utf-8")
    for forbidden in ("expected_goal", "sealed", "instance_sha256", "constraints",
                      "evaluate", "verdict"):
        pattern = r"[\"']%s[\"']" % forbidden
        assert not re.search(pattern, src), "the rule planner reads " + forbidden

    print(json.dumps({
        "verdict": "EVOBOT_BENCHMARK_SATURATED_AT_PLANNING",
        "instances": n,
        "deterministic_parser_correct": "%d/%d" % (rule_ok, n),
        "llm_correct": "%d/%d" % (llm_ok, n),
        "agreement": "%d/%d" % (agree, n),
        "meaning": ("these three templates cannot show that the LLM is necessary; a regex "
                    "matches it"),
        "not_claimed": ("that the LLM is useless in general, or that the parser generalizes "
                        "- it was written after the templates were known"),
        "level_8_effect": "must be downgraded: a saturatable benchmark cannot prove reasoning",
        "evaluator_touched": False,
        "skill_layer_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
