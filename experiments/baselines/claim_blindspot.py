#!/usr/bin/env python3
"""Before trusting a deterministic claim, ask what it is BLIND to.

The deterministic check compares measured positions against the PLAN's targets. If the plan
itself names the wrong bin, the objects can sit exactly on the plan's targets, the check will
say "satisfied", and the claim will be True while the evaluator fails - a false success.

That risk is invisible in this data because every plan was correct. So measure the ingredient
that would create it: how far are plan targets from the zone centre, relative to the acceptance
radius? A target deep inside its zone gives the check room to be wrong safely; a target near the
edge does not.
"""
import glob
import json
import math
import os
import sys

WT = "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp"
BATCHES = ["/tmp/evobot-batch1", "/tmp/evobot-batch2",
           "/tmp/evobot-batch3", "/tmp/evobot-batch4"]


def read(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def main():
    margins = []
    plans_with_wrong_shape = 0
    for base in BATCHES:
        for d in sorted(glob.glob(os.path.join(base, "HO-*"))):
            plan = read(os.path.join(d, "plan.json")) or {}
            obs = read(os.path.join(d, "observation_input.json")) or {}
            zones = obs.get("zones") or []
            if not zones:
                continue
            for st in plan.get("stages", []):
                pose = st.get("place_pose")
                if not pose:
                    continue
                best = None
                for z in zones:
                    c = z["position"]
                    dd = math.hypot(pose[0] - c[0], pose[1] - c[1])
                    if best is None or dd < best[0]:
                        best = (dd, z.get("radius", 0.06))
                margins.append((os.path.basename(d), best[0], best[1]))
    if not margins:
        print("no plans found")
        return 0
    tightest = sorted(margins, key=lambda m: m[2] - m[1])[:8]
    print("plan targets, distance from NEAREST zone centre vs that zone's radius:")
    print("%-20s %-12s %-8s %s" % ("run", "distance_m", "radius_m", "slack_m"))
    for oid, d_, r_ in tightest:
        print("%-20s %-12.4f %-8.3f %.4f" % (oid, d_, r_, r_ - d_))
    inside = [m for m in margins if m[1] <= m[2]]
    print()
    print("stage targets examined        :", len(margins))
    print("inside their zone             :", len(inside))
    print("outside (would be a bad plan) :", len(margins) - len(inside))
    if inside:
        worst = min(inside, key=lambda m: m[2] - m[1])
        print("tightest slack                : %.1f mm" % (1000 * (worst[2] - worst[1])))
    print()
    print("WHAT THIS MEANS FOR A DETERMINISTIC CLAIM: it verifies EXECUTION against the plan,")
    print("not the plan against the instruction. With every plan correct that is invisible;")
    print("one wrong plan and it would report success while the evaluator fails. Nothing in")
    print("this archive can rule that out, so the check is NOT adopted as the agent claim.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
