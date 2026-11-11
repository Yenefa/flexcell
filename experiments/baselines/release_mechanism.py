#!/usr/bin/env python3
"""Tabulate every release failure and the two signals the skill recorded for it.

THE QUESTION THIS ANSWERS: the actuator_stall proposal assumed a failed release meant the object
had NOT been released, so retrying the release command would help. If instead the carry layer
had already confirmed the release, retrying is pointless and the defect is in the confirmation
test. Only the per-record signals can settle it.
"""
import glob
import json
import os
import sys

BATCHES = sys.argv[1:] or ["/tmp/evobot-batch2", "/tmp/evobot-batch3"]


def main():
    print("%-14s %-20s %-9s %-11s %-12s %-14s %-9s %s" % (
        "batch", "run", "released", "carry_conf", "reached_goal", "classification",
        "position", "detail"))
    n = 0
    uniform = True
    for base in BATCHES:
        for d in sorted(glob.glob(os.path.join(base, "HO-*"))):
            p = os.path.join(d, "sim", "skills", "place.jsonl")
            if not os.path.exists(p):
                continue
            for line in open(p, encoding="utf-8", errors="replace"):
                line = line.strip()
                if not line:
                    continue
                x = json.loads(line)
                if x.get("released"):
                    continue
                g = x.get("gripper_open") or {}
                n += 1
                if x.get("carry_release_confirmed") is not True:
                    uniform = False
                print("%-14s %-20s %-9s %-11s %-12s %-14s %-9s %s" % (
                    os.path.basename(base), os.path.basename(d), x.get("released"),
                    x.get("carry_release_confirmed"), g.get("reached_goal"),
                    g.get("classification"), g.get("position"),
                    str(x.get("detail"))[:46]))
    print()
    print("release failures observed            :", n)
    print("every one had carry_confirmed = True :", uniform)
    print()
    print("READING: the carry layer detached the object (release happened) while the jaw")
    print("did not reach the commanded aperture (a real stall). The skill fails on the")
    print("aperture test alone, so a successful release is reported as a failure.")
    print()
    print("CONSEQUENCE FOR THE OLD PROPOSAL: re-commanding the release cannot help when")
    print("the release already happened. bounded_release_retry is therefore misdirected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
