#!/usr/bin/env python3
"""C13e: splitting the PLACE batch into 2+1 stages was rejected and REVERTED.

Asserts that the code is back to the 3-stage contract, i.e. the failed attempt left
no residue, and that the preregistration recording the attempt still exists.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parents[2]
PLACE = REPO / "src/flexcell/flexcell_skills/flexcell_skills/place_server.py"
PRE = REPO / "docs/C13E_PREREGISTRATION.md"


def main():
    place = PLACE.read_text(encoding="utf-8")

    # the revert really happened: the 3-stage batch is back
    assert re.search(r"\[hover, descend, retreat\]", place), \
        "the original 3-stage batch is not present; revert incomplete"
    # and no trace of the rejected 2-stage attempt remains
    assert "retreat_replanned" not in place, "the reverted patch is still in the tree"
    assert "[retreat], profile" not in place, "the 2+1 split is still present"

    # the preregistration that governs this attempt is on disk
    assert PRE.exists(), "preregistration missing"
    pre = PRE.read_text(encoding="utf-8")
    assert "H1" in pre and "回退" in pre, "preregistration lacks the outcome/rollback rule"

    print(json.dumps({
        "verdict": "C13E_STAGE_SPLIT_REJECTED_AND_REVERTED",
        "pre_registered": "H1: 2+1 split makes retreat start measured",
        "actual": "H0 plus a regression on the default world",
        "planner_error": "invalid operation, object, profile or stage count",
        "cause": "PLACE requires exactly 3 stages; 2 was rejected outright",
        "reverted": True,
        "residue": "none - only the preregistration doc remains",
        "implication": "C13d root cause stands; fix (a) needs a planner contract change",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
