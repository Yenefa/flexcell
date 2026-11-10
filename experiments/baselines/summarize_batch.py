#!/usr/bin/env python3
"""Summarise a T05 batch with the three layers kept separate.

The first batch I ran conflated three different failures and would have produced a
misleading "success rate". A task can fail because:

  PLANNING   the arm could not produce a plan from the instruction;
  EXECUTION  the plan was fine but the robot could not carry it out;
  HARNESS    my own script or the simulator fell over (crash, missing key, bad path).

Averaging those into one number would let me blame the agent for my own bugs, or claim
agent capability from runs that never executed.
"""
import glob
import json
import os
import sys


def layer_of(d):
    """Return (layer, detail) describing how far this attempt got."""
    task = os.path.join(d, "task.out")
    verdict = os.path.join(d, "verdict.json")
    if not os.path.exists(task):
        return "HARNESS", "no task.out (never dispatched)"
    text = open(task, encoding="utf-8", errors="replace").read()
    if "RESULT " not in text:
        if "RCLError" in text or "action server unavailable" in text:
            return "HARNESS", "stack unavailable"
        return "HARNESS", "client produced no terminal result"
    result = json.loads(text.split("RESULT ", 1)[1])
    if not result.get("ok"):
        return "HARNESS", result.get("error", "")[:60]
    if result.get("outcome") != 0:
        return "EXECUTION", "err %s: %s" % (result.get("error_code"),
                                            (result.get("detail") or "")[:60])
    if not os.path.exists(verdict):
        return "HARNESS", "no verdict file"
    try:
        v = json.load(open(verdict, encoding="utf-8"))
    except Exception:
        return "HARNESS", "verdict unreadable"
    if v.get("passed"):
        return "PASS", "all clauses ok"
    return "GRADED_FAIL", ",".join(v.get("failed_clauses") or [])[:80]


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ev-t05-robust"
    seeds = sorted({os.path.basename(p).split("-")[0] for p in glob.glob(base + "/s*")})
    rows = []
    for seed in seeds:
        attempts = sorted(glob.glob(os.path.join(base, seed + "-a*")))
        best = None
        for d in attempts:
            layer, detail = layer_of(d)
            if layer == "PASS":
                best = (d, layer, detail)
                break
            if best is None or best[1] == "HARNESS":
                best = (d, layer, detail)
        ap = os.path.join(base, seed + "-a1", "a_prime.json")
        planned = None
        if os.path.exists(ap):
            try:
                planned = json.load(open(ap))["planned"]
            except Exception:
                planned = None
        rows.append((seed, planned, best[1], best[2], len(attempts)))

    print("%-9s %-10s %-13s %-6s %s" % ("seed", "A_prime", "layer", "tries", "detail"))
    for seed, planned, layer, detail, tries in rows:
        print("%-9s %-10s %-13s %-6d %s" % (seed, planned, layer, tries, detail))

    counts = {}
    for _, _, layer, _, _ in rows:
        counts[layer] = counts.get(layer, 0) + 1
    n = len(rows)
    infra = counts.get("HARNESS", 0)
    attempted = n - infra
    print()
    print("instances            :", n)
    print("A_prime planned      :", sum(1 for _, p, _, _, _ in rows if p), "/", n)
    print("layer counts         :", counts)
    print("executed (non-harness):", attempted)
    if attempted:
        ok = counts.get("PASS", 0)
        print("PASS among executed   : %d/%d = %.0f%%" % (ok, attempted, 100.0 * ok / attempted))
    return 0


if __name__ == "__main__":
    sys.exit(main())
