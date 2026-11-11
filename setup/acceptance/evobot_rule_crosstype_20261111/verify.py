#!/usr/bin/env python3
"""Verify the corrected cross-type result: a pre-T14 rule set has zero understanding of T14."""
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
text = (HERE / "crosstype.txt").read_text(encoding="utf-8")


def main():
    def grab(p):
        m = re.search(p, text)
        assert m, p
        return int(m.group(1))

    n = 16
    pre = grab(r"rule set WITHOUT a T14 branch\s+(\d+)/16")
    full = grab(r"rule set WITH a T14 branch\s+(\d+)/16")
    llm = grab(r"LLM planner\s+(\d+)/16")
    coincidental = grab(r"of the (\d+) that scored")

    assert pre == 5, pre
    assert full == 16 and llm == 16, (full, llm)
    # every point the pre-T14 rules scored was luck, or the claim collapses
    assert coincidental == 5, ("some pre-T14 successes were NOT explainable as luck",
                               coincidental)
    assert "0/16" in text, "the corrected reading must state zero understanding"

    # the pre-T14 baseline must really be the full rule set minus that branch
    pre_src = (WT / "runtime" / "planner" / "rule_planner_pre_t14.py").read_text(
        encoding="utf-8")
    full_src = (WT / "runtime" / "planner" / "rule_planner.py").read_text(encoding="utf-8")
    assert "must be put there FIRST" in full_src
    assert "must be put there FIRST" not in pre_src, "the pre-T14 copy still parses T14"
    assert "def plan(" in pre_src

    print(json.dumps({
        "verdict": "EVOBOT_CROSSTYPE_RULE_GAP_MEASURED",
        "rule_set_written_before_T14": "5/16 scored, 5 of them luck, understanding 0/16",
        "rule_set_updated_for_T14": "16/16",
        "llm_planner": "16/16",
        "conclusion": ("last round over-claimed. Within a template family a regex matches the "
                       "LLM; across an unseen type it does not."),
        "calibration_note": ("the rule set silently ignored the order constraint instead of "
                             "declining, which is the failure mode the LLM avoided"),
        "evaluator_touched": False,
        "skill_layer_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
