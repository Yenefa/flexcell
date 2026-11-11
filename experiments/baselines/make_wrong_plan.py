#!/usr/bin/env python3
"""Build an EXECUTABLE but WRONG plan from an archived one, and verify it really changed.

WHY THIS EXISTS AS A FILE: three earlier probe attempts were heredocs, and two of them failed in
ways that could have produced a passing-looking result - one lost its swap to a syntax error
with no set -e, another mapped both objects onto the same pose so the executor refused to move
anything. A probe whose setup can fail silently is not a probe. This module either produces a
verified wrong plan or exits non-zero.

THE WRONG PLAN MIRRORS each stage into the OTHER zone and spreads the stages along x so they stay
separated - the point is a plan that the robot WILL execute, because a plan it refuses tells us
nothing about whether the claim check can be fooled.
"""
import json
import math
import sys

ZONES = {"zone_1": [0.12, -0.15, 0.0175], "zone_2": [0.25, 0.05, 0.0175]}
SWAP = {"zone_1": "zone_2", "zone_2": "zone_1"}
SPREAD_STEP_M = 0.045


def main():
    src, dst = sys.argv[1], sys.argv[2]
    plan = json.load(open(src, encoding="utf-8"))
    stages = plan.get("stages", [])
    n = len(stages)
    if n == 0:
        raise SystemExit("FATAL: source plan has no stages")
    print("  original:", [(s["object_name"], s["place_pose"]) for s in stages])
    for i, st in enumerate(stages):
        pose = st.get("place_pose")
        if not pose:
            continue
        cur = min(ZONES, key=lambda z: math.hypot(pose[0] - ZONES[z][0],
                                                  pose[1] - ZONES[z][1]))
        target = ZONES[SWAP[cur]]
        spread = SPREAD_STEP_M * (i - (n - 1) / 2.0) if n > 1 else 0.0
        st["place_pose"] = [target[0] + spread, target[1], target[2]]
    posed = [tuple(round(v, 3) for v in st["place_pose"][:2]) for st in stages]
    if len(set(posed)) != len(posed):
        raise SystemExit("FATAL: mirrored stages still collide: %s" % (posed,))
    original = json.load(open(src, encoding="utf-8"))
    if [s["place_pose"] for s in original["stages"]] == [s["place_pose"] for s in stages]:
        raise SystemExit("FATAL: plan was not modified")
    json.dump(plan, open(dst, "w", encoding="utf-8"), indent=2)
    print("  wrong   :", [(s["object_name"], [round(v, 3) for v in s["place_pose"]])
                          for s in stages])
    print("  verified: modified and stages are distinct")
    return 0


if __name__ == "__main__":
    sys.exit(main())
