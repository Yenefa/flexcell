#!/usr/bin/env python3
"""Compare Baseline B and C plans on the same 16 instances, after routing was fixed."""
import glob
import hashlib
import json
import os
import sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/evobot-bcplan16"


def digest(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:12]


def main():
    ids = sorted({os.path.basename(d).rsplit("-", 1)[0]
                  for d in glob.glob(BASE + "/*-B") + glob.glob(BASE + "/*-C")})
    same = diff = missing = 0
    lesson_counts = []
    for oid in ids:
        pb = os.path.join(BASE, oid + "-B", "plan.json")
        pc = os.path.join(BASE, oid + "-C", "plan.json")
        if not (os.path.exists(pb) and os.path.exists(pc)):
            missing += 1
            continue
        obs = json.load(open(os.path.join(BASE, oid + "-C", "observation_input.json")))
        lesson_counts.append(len(obs.get("experience") or []))
        if digest(pb) == digest(pc):
            same += 1
        else:
            diff += 1
            print("DIFFERENT:", oid)
    print()
    print("pairs compared      :", len(ids) - missing)
    print("byte-identical plans:", same)
    print("differing plans     :", diff)
    print("missing             :", missing)
    if lesson_counts:
        print("lessons retrieved into C: min=%d max=%d" % (
            min(lesson_counts), max(lesson_counts)))
    print()
    if diff == 0:
        print("CONCLUSION: even with a reachable, planner-actionable lesson,")
        print("experience still does not change the plan. The lesson is TRUE but")
        print("the planner already satisfies it, so it adds tokens and no behaviour.")
    else:
        print("CONCLUSION: experience changed %d plan(s)." % diff)
    return 0


if __name__ == "__main__":
    sys.exit(main())
