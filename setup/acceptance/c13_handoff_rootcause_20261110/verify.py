#!/usr/bin/env python3
"""C13b: the MTC handoff failure is UNDIAGNOSED. This verifier asserts that.

It exists to stop anyone (including me) from turning a plausible story into a
finding. Two wrong explanations were already published and retracted:

  1. "the guard has no tolerance"      -> false, it is `> .03`;
  2. "the gripper moved 0.031 rad"     -> false, the guard only iterates the
                                          trajectory joint names, which are the
                                          four arm joints.

What can be asserted is narrow: the guard fired, its tolerance is 0.03, it only
compares arm joints, and the trajectory start position - the other side of the
comparison - is not recorded, so the delta is unknown from archived data.
"""
import glob
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parents[2] / "src/flexcell/flexcell_skills/flexcell_skills/move_to_pose_server.py"


def main():
    src = REPO.read_text(encoding="utf-8")
    i = src.find("measured start state differs")
    assert i > 0, "guard not found"
    guard = src[max(0, i - 400):i]
    # the tolerance exists - this is the fact I got wrong first
    assert re.search(r"positions\[i\]\)\s*>\s*\.03", guard), guard
    # the comparison is against the trajectory start, not the previous run
    assert "trajectory.joint_trajectory.points[0].positions[i]" in guard, guard
    # only arm joints are iterated
    assert "trajectory.joint_trajectory.joint_names" in guard, guard

    run = glob.glob(str(HERE.parent / "c13_constrained_20261110/mtc/run-*"))[0]
    rows = [json.loads(l) for l in
            (Path(run) / "skills/move_to_pose.jsonl").read_text().splitlines() if l.strip()]
    bad = [r for r in rows if r.get("outcome") == "FAILED"]
    assert bad, "no failed record"
    names = (bad[0].get("final_joint_state") or {}).get("name") or []
    # measured state carries the gripper, but the guard never looks at it
    assert "gripper_left_joint" in names, names
    ok = [r for r in rows if r.get("outcome") == "SUCCEEDED"][-1]
    assert ok["planned_joint_names"] == ["joint1", "joint2", "joint3", "joint4"], \
        ok["planned_joint_names"]

    print(json.dumps({
        "verdict": "C13B_HANDOFF_FAILURE_UNDIAGNOSED",
        "guard_has_tolerance_rad": 0.03,
        "guard_iterates": "trajectory.joint_trajectory.joint_names (4 arm joints)",
        "gripper_involved": False,
        "trajectory_start_recorded": False,
        "delta": "UNKNOWN - the other side of the comparison is not logged",
        "retracted_explanations": [
            "no tolerance in the guard",
            "gripper moved 0.031 rad and tripped the check",
        ],
        "next_step": "log trajectory.points[0].positions in _consume_mtc, then rerun",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
