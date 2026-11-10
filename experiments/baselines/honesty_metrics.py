#!/usr/bin/env python3
"""Audit the honesty metrics in both directions, not just false success.

WHY: I have been reporting "false success 0/32" every round. That number is only
meaningful if the agent's self-assessment is actually recorded for every run, and it says
nothing about the OPPOSITE error - an agent that claims failure after succeeding. Both
directions matter: false success is dangerous, false failure is useless.

This reads archived verdicts only. It changes no grading.
"""
import glob
import json
import math
import os
import sys

BATCHES = ["/tmp/evobot-pair16", "/tmp/evobot-pair32"]


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def main():
    rows = []
    for base in BATCHES:
        for d in sorted(glob.glob(os.path.join(base, "HO-*"))):
            v = os.path.join(d, "verdict.json")
            if not os.path.exists(v):
                continue
            try:
                doc = json.load(open(v, encoding="utf-8"))
            except Exception:
                continue
            rows.append({
                "id": os.path.basename(d),
                "claim": doc.get("agent_claimed_success"),
                "passed": doc.get("passed"),
                "fs": bool(doc.get("false_success")),
                "ff": bool(doc.get("false_failure")),
            })

    n = len(rows)
    missing = sum(1 for r in rows if r["claim"] is None)
    fs = sum(1 for r in rows if r["fs"])
    ff = sum(1 for r in rows if r["ff"])
    claimed_ok = sum(1 for r in rows if r["claim"] is True)
    actually_ok = sum(1 for r in rows if r["passed"] is True)

    print("verdicts                 :", n)
    print("agent claim recorded     :", n - missing)
    print("claim missing (vacuous 0):", missing)
    print()
    print("agent CLAIMED success    : %d/%d" % (claimed_ok, n))
    print("ACTUALLY passed          : %d/%d" % (actually_ok, n))
    p, lo, hi = wilson(fs, n)
    print("FALSE SUCCESS            : %d/%d = %.1f%% (%.1f-%.1f%%)"
          % (fs, n, 100 * p, 100 * lo, 100 * hi))
    p2, lo2, hi2 = wilson(ff, n)
    print("FALSE FAILURE            : %d/%d = %.1f%% (%.1f-%.1f%%)"
          % (ff, n, 100 * p2, 100 * lo2, 100 * hi2))
    print()
    if missing:
        print("WARNING: %d verdict(s) carry no agent claim, so their zero is vacuous."
              % missing)
    else:
        print("Every verdict carries an agent claim, so the false-success zero is MEASURED.")
    print()
    print("Both directions matter: false success is dangerous, false failure is useless.")
    print("An agent that under-claims looks safe here while being less useful than")
    print("its actual competence - which would mislead anyone reading only false success.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
