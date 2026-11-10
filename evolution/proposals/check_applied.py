#!/usr/bin/env python3
"""Check a proposal against REAL code behaviour, not against prose.

A proposal that merely describes a change proves nothing. This module rebuilds the exact
failing scenario from the archived evidence and asks the CURRENT code whether it would
still produce that failure. That separates two very different claims:

  ALREADY_SATISFIED - current code already handles the measured scenario, so the
                     proposal is a RETROSPECTIVE reconstruction, not a new discovery.
  WOULD_FIX        - current code still fails the scenario, so the proposal is the
                     change that would fix it.

Calling a retrospective reconstruction "self-improvement" would be dishonest, so the
label is computed rather than written.
"""
import json
import math
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "experiments", "baselines"))
import spread_destinations as sd

CLEARANCE = 0.05
DRIFT = 0.010


def check_occupied_destination():
    z = [0.12, -0.15, 0.0175]
    stages = [{"object_name": "a", "place_pose": list(z)},
              {"object_name": "a", "place_pose": list(z)}]
    avoid = [[0.20, -0.18]]
    try:
        out = sd.spread(stages, avoid=avoid)
    except ValueError as exc:
        return "REFUSED", str(exc)
    worst = None
    for s in out:
        for ax, ay in avoid:
            d = math.hypot(s["place_pose"][0] - ax, s["place_pose"][1] - ay)
            worst = d if worst is None else min(worst, d)
    gap = None
    if len(out) >= 2:
        gap = math.hypot(out[1]["place_pose"][0] - out[0]["place_pose"][0],
                         out[1]["place_pose"][1] - out[0]["place_pose"][1])
    ok = (worst is not None and worst >= CLEARANCE
          and gap is not None and gap >= CLEARANCE + DRIFT)
    return ("ALREADY_SATISFIED" if ok else "WOULD_FIX",
            "worst distance to avoided object %.3f m, spacing %.3f m" % (
                worst if worst is not None else -1.0,
                gap if gap is not None else -1.0))


CHECKS = {"occupied_destination": check_occupied_destination}


def main():
    pd = os.path.join(WT, "evolution", "proposals")
    files = sorted(f for f in os.listdir(pd) if f.endswith(".json")) if os.path.isdir(pd) else []
    if not files:
        print("no proposals on disk")
        return 0
    for f in files:
        doc = json.load(open(os.path.join(pd, f), encoding="utf-8"))
        check = CHECKS.get(doc.get("signature"))
        if check is None:
            print("%-30s NO BEHAVIOURAL CHECK" % f)
            continue
        label, why = check()
        print("%-30s %-18s %s" % (f, label, why))
    return 0


if __name__ == "__main__":
    sys.exit(main())
