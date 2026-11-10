#!/usr/bin/env python3
"""Regression check: did the spacing change break any previously verified v0.1 task?

A regression is not "the new number looks fine". It is a per-task comparison against the
frozen baseline: every task that passed before must still pass, and any newly failing
task is a regression regardless of the aggregate.
"""
import glob
import json
import os
import sys

BEFORE = ("/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp"
          "/setup/acceptance/evobot_heldout_n6_20261111/runs")
AFTER = "/tmp/evobot-regress-v01"


def load_pass(d):
    v = os.path.join(d, "verdict.json")
    if not os.path.exists(v):
        return None
    try:
        return json.load(open(v)).get("passed")
    except Exception:
        return None


def outcome(d):
    t = os.path.join(d, "task.out")
    if not os.path.exists(t) or "RESULT " not in open(t).read():
        return None
    return json.loads(open(t).read().split("RESULT ", 1)[1]).get("outcome")


def main():
    rows = []
    for d in sorted(glob.glob(AFTER + "/*_B")):
        oid = os.path.basename(d).rsplit("_", 1)[0]
        before = os.path.join(BEFORE, oid)
        rows.append((oid, load_pass(before), outcome(before),
                     load_pass(d), outcome(d)))
    print("%-20s %-8s %-7s %-8s %-7s %s" % (
        "task", "before", "o/out", "after", "o/out", "verdict"))
    regressions = []
    for oid, b, bo, a, ao in rows:
        note = ""
        if b is True and a is not True:
            note = "REGRESSION"
            regressions.append(oid)
        elif b is False and a is True:
            note = "improved"
        print("%-20s %-8s %-7s %-8s %-7s %s" % (oid, b, bo, a, ao, note))
    ok_before = sum(1 for _, b, _, _, _ in rows if b is True)
    ok_after = sum(1 for _, _, _, a, _ in rows if a is True)
    print()
    print("before PASS : %d/%d" % (ok_before, len(rows)))
    print("after  PASS : %d/%d" % (ok_after, len(rows)))
    print("REGRESSIONS : %s" % (regressions if regressions else "NONE"))
    return 0 if not regressions else 1


if __name__ == "__main__":
    sys.exit(main())
