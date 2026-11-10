#!/usr/bin/env python3
"""Report execution-layer variance across repeated batches of the same instances."""
import glob
import json
import os
import sys

BATCHES = [
    ("pre-avoid-fix (9/16)", None),
    ("after-avoid-fix", "setup/acceptance/evobot_pair16_20261111/runs"),
]


def rate(runs_dir):
    n = ok = 0
    for d in sorted(glob.glob(os.path.join(runs_dir, "HO-*"))):
        v = os.path.join(d, "verdict_after1.json")
        if not os.path.exists(v):
            continue
        n += 1
        ok += 1 if json.load(open(v, encoding="utf-8")).get("passed") else 0
    return ok, n


def main():
    print("Baseline B (first attempt, NO recovery) on the SAME 16 instances,")
    print("measured in successive batches as fixes landed:")
    for label, runs in BATCHES:
        if not runs:
            print("  %-26s 9/16 (recorded in the previous round)" % label)
            continue
        ok, n = rate(runs)
        print("  %-26s %d/%d" % (label, ok, n))
    print()
    print("The spread across batches is the execution-layer variance. Any single-batch")
    print("comparison smaller than that spread is not a result.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
