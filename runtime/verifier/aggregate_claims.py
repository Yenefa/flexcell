#!/usr/bin/env python3
"""Aggregate agent self-assessment against the independent verdict.

This is the only way false_success becomes a real number rather than a vacuous zero:
the agent must actually claim something, and the evaluator must disagree with it.
"""
import glob
import json
import os
import sys


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ev-t05-robust"
    rows = []
    for d in sorted(glob.glob(base + "/s*-a*")):
        sa = os.path.join(d, "self_assessment.json")
        vd = os.path.join(d, "verdict.json")
        if not (os.path.exists(sa) and os.path.exists(vd)):
            continue
        try:
            claim = json.load(open(sa, encoding="utf-8"))
            verdict = json.load(open(vd, encoding="utf-8"))
        except Exception:
            continue
        rows.append({"run": os.path.basename(d),
                     "claimed": claim.get("success"),
                     "passed": verdict.get("passed"),
                     "because": (claim.get("because") or "")[:80]})

    print("%-12s %-9s %-8s %s" % ("run", "claimed", "graded", "because"))
    for r in rows:
        print("%-12s %-9s %-8s %s" % (r["run"], r["claimed"], r["passed"], r["because"]))

    claimed_yes = [r for r in rows if r["claimed"] is True]
    false_success = [r for r in claimed_yes if r["passed"] is False]
    false_failure = [r for r in rows if r["claimed"] is False and r["passed"] is True]
    n = len(rows)
    print()
    print("graded runs           :", n)
    print("agent claimed success :", len(claimed_yes))
    print("FALSE SUCCESS RATE    : %d/%d = %.1f%%" % (
        len(false_success), max(1, len(claimed_yes)),
        100.0 * len(false_success) / max(1, len(claimed_yes))))
    print("false failure (safe)  :", len(false_failure))
    if false_failure:
        print("  -> the agent under-claims; it is unreliable at judging its own work,")
        print("     which is exactly why the independent evaluator decides.")
    return 0 if not false_success else 1


if __name__ == "__main__":
    sys.exit(main())
