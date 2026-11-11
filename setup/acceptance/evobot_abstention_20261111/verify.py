#!/usr/bin/env python3
"""Verify the archived abstention probe: no impossible instruction was confidently answered."""
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
spec = importlib.util.spec_from_file_location(
    "ab", WT / "experiments" / "baselines" / "abstention.py")
AB = importlib.util.module_from_spec(spec)
spec.loader.exec_module(AB)


def main():
    text = (HERE / "probe.txt").read_text(encoding="utf-8")

    # the recorded run must report the promised numbers
    m = re.search(r"CONFIDENTLY ANSWERED \(the defect\)\s*:\s*(\d+)", text)
    assert m, "the probe output is missing its summary line"
    assert int(m.group(1)) == 0, "an impossible instruction was confidently answered"
    m = re.search(r"refused\s*:\s*(\d+)", text)
    assert m and int(m.group(1)) == 4, text[-400:]
    m = re.search(r"flagged \(not high confidence\)\s*:\s*(\d+)", text)
    assert m and int(m.group(1)) == 4, text[-400:]

    # the probe design itself must keep the controls, or refusal would score perfectly
    kinds = [c[1] for c in AB.CASES]
    assert kinds.count("IMPOSABLE") == 8, kinds.count("IMPOSABLE")
    assert kinds.count("POSSIBLE") == 2

    # every recorded case line must exist and say "ok"
    for case_id, _, _ in AB.CASES:
        line = [l for l in text.splitlines() if l.startswith(case_id)]
        assert line, case_id
        assert " ok " in line[0], (case_id, line[0])

    print(json.dumps({
        "verdict": "EVOBOT_ABSTENTION_MEASURED",
        "impossible_instructions": 8,
        "refused": 4,
        "flagged_with_a_specific_reason": 4,
        "confidently_answered": 0,
        "possible_controls_answered": "2/2",
        "what_this_bounds": ("last round claimed 0/64 planner failures; this probes the "
                             "boundary with tasks that have no correct plan"),
        "caveats": "n=10, one model, temperature 0, self-authored probes",
        "robot_runs": 0,
        "evaluator_touched": False,
        "skill_layer_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
