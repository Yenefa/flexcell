#!/usr/bin/env python3
"""C13d: the retreat fails because stages are planned as a batch, so stage N+1
starts at the PREDICTED end of stage N while the guard demands the MEASURED state.

Also asserts that the 0.03 rad tolerance was NOT relaxed: the point of this record
is that the failure was explained, not that it was made to pass.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parents[2]
PLACE = REPO / "src/flexcell/flexcell_skills/flexcell_skills/place_server.py"
SERVER = REPO / "src/flexcell/flexcell_skills/flexcell_skills/move_to_pose_server.py"


def main():
    place = PLACE.read_text(encoding="utf-8")
    server = SERVER.read_text(encoding="utf-8")

    assert re.search(r"mtc\.prepare\([^)]*\[hover, descend, retreat\]", place), \
        "place_server no longer batch-plans [hover, descend, retreat]"

    i = server.find("measured start state differs")
    assert i > 0
    window = server[max(0, i - 1200):i]
    bounded = (re.search(r"d > \.03", window)
               or re.search(r"positions\[i\]\)\s*>\s*\.03", window))
    assert bounded, "the start-state tolerance was changed"

    print(json.dumps({
        "verdict": "C13D_RETREAT_BATCH_PLANNING_PREDICTION_GAP",
        "batch_planned_stages": ["hover", "descend", "retreat"],
        "retreat_start_is": "predicted end of descend, not measured",
        "observed_delta_rad": 0.05292,
        "tolerance_rad": 0.03,
        "tolerance_relaxed": False,
        "object_placed": True,
        "mtc_completed_task": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
