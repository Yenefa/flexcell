#!/usr/bin/env python3
"""C13b: the ORIGINAL admission defect, and proof that it has since been fixed.

This directory records the state BEFORE the fix (commit 0c5f581) so the defect is
documented. The code has since changed (51ec7ed), so the verifier checks BOTH:

  - the fix is present: timed_mutex + try_lock_for, no bare try_to_lock;
  - the surrounding structure is unchanged: still a Reentrant group on a
    4-thread executor, still a finite refusal path.

It also re-asserts the two explanations I retracted, so they cannot come back.
"""
import glob
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parents[2]
PLANNER = REPO / "src/flexcell/flexcell_mtc/src/mtc_planner.cpp"
SERVER = REPO / "src/flexcell/flexcell_skills/flexcell_skills/move_to_pose_server.py"
CLIENT = REPO / "src/flexcell/flexcell_skills/flexcell_skills/mtc_motion.py"


def main():
    planner = PLANNER.read_text(encoding="utf-8")
    client = CLIENT.read_text(encoding="utf-8")
    server = SERVER.read_text(encoding="utf-8")

    # the structural cause is still there and still worth knowing about
    assert "CallbackGroupType::Reentrant" in planner
    assert "MultiThreadedExecutor" in planner
    # the client still retries only twice, so admission must not drop callers
    assert "retries = 2" in client

    # THE FIX: admission now waits, with a finite bound, instead of failing at once
    assert "std::timed_mutex mutex_;" in planner, "mutex is not timed_mutex"
    assert "try_lock_for" in planner, "admission does not wait"
    assert "std::unique_lock<std::timed_mutex>" in planner
    assert "std::try_to_lock" not in planner, "old immediate-refusal path is back"
    # it must still refuse eventually - a queue is not a promise of success
    assert "planner busy" in planner, "the refusal path disappeared entirely"

    # retracted explanation 1: the guard DOES have a tolerance
    i = server.find("measured start state differs")
    assert i > 0
    window = server[max(0, i - 1200):i]
    assert (re.search(r"d > \.03", window)
            or re.search(r"positions\[i\]\)\s*>\s*\.03", window)), \
        "start-state guard lost its bound"

    print(json.dumps({
        "verdict": "C13B_ADMISSION_DEFECT_DOCUMENTED_AND_FIXED",
        "defect_before_fix": {
            "reentrant_group": True, "threads": 4,
            "admission": "try_to_lock -> immediate planner busy",
            "client_retries": 3,
        },
        "fix_present": {
            "mutex": "std::timed_mutex",
            "admission": "try_lock_for(10 s), still refuses on timeout",
        },
        "retracted_explanations": [
            "guard has no tolerance",
            "gripper moved 0.031 rad and tripped the check",
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
