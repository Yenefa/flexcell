#!/usr/bin/env python3
"""Measure the base rate a bounded release retry could plausibly achieve.

WHY BEFORE APPLYING: the proposal claims "phases that failed only because the first
release stalled will succeed". Without a measured base rate that claim is a wish, and any
result afterwards could be spun either way. This script derives the number from archived
evidence so the prediction is committed BEFORE the change is made.

It separates three populations among runs where a release stall appeared:
  absorbed  - a later stage execution succeeded inside the same run
  persistent- every stage execution that ran stalled again
That ratio is the ceiling for what a retry can buy, and persistence is the floor it cannot.
"""
import glob
import json
import math
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "runtime", "recovery"))
import execution_root_cause as E

BATCHES = ["/tmp/evobot-pair16", "/tmp/evobot-pair32"]


def stall_episodes(run_dir):
    """(index, stalled) for each episode, in execution order."""
    eps = sorted(glob.glob(os.path.join(run_dir, "sim", "episodes", "*.json")),
                 key=os.path.getmtime)
    out = []
    for i, ep in enumerate(eps):
        fails = E.episode_failures(ep)
        out.append((i, any("did not open" in (f["detail"] or "") for f in fails)))
    return out


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def main():
    absorbed = persistent = 0
    rows = []
    for base in BATCHES:
        for d in sorted(glob.glob(os.path.join(base, "HO-*"))):
            eps = stall_episodes(d)
            stalls = [i for i, s in eps if s]
            if not stalls:
                continue
            b = os.path.join(d, "verdict_after1.json")
            r = os.path.join(d, "verdict.json")
            if not (os.path.exists(b) and os.path.exists(r)):
                continue
            bd = json.load(open(b, encoding="utf-8"))
            rd = json.load(open(r, encoding="utf-8"))
            # did a LATER episode succeed after a stall?
            later_ok = any(i > stalls[0] and not s for i, s in eps)
            if rd.get("passed") and (later_ok or len(stalls) == 1):
                absorbed += 1
                kind = "absorbed"
            else:
                persistent += 1
                kind = "persistent"
            rows.append((os.path.basename(d), len(stalls), bd.get("passed"),
                         rd.get("passed"), kind))
    print("%-20s %-6s %-6s %-6s %s" % ("run", "stalls", "B", "R", "outcome"))
    for r in rows:
        print("%-20s %-6d %-6s %-6s %s" % r)
    n = absorbed + persistent
    p, lo, hi = wilson(absorbed, n)
    print()
    print("runs where a release stall appeared :", n)
    print("resolved on a later execution      : %d" % absorbed)
    print("persistent (stalled again)          : %d" % persistent)
    print("BASE RATE a bounded retry can reach : %.0f%% (%.0f-%.0f%% Wilson 95%%)"
          % (100 * p, 100 * lo, 100 * hi))
    print()
    print("PRE-REGISTERED PREDICTION for a bounded release retry:")
    print("  - it can recover at most the absorbed fraction, %.0f%%" % (100 * p))
    print("  - a persistent stall MUST still fail; if it passes, the retry is")
    print("    converting real failures into passes and must be reverted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
