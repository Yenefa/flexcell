#!/usr/bin/env python3
"""Three-way comparison of the self-assessment prompt versions, against ground truth.

WHY THREE AND NOT TWO: v1 mistook the plan for execution (1 false success). v2 fixed that
but over-corrected - it told the assessor to ignore the plan entirely and cut false success
to zero while breaking six correct verdicts, dropping accuracy 62.5% -> 53.1%. A zero
bought by being pessimistic is not a fix, it is a different error. v3 keeps only the
FACTUAL corrections (the plan is intent; an empty release list is NONE) and drops the
blanket distrust. This script reports all three so the trade-off is visible rather than
hidden behind whichever version flatters the number.
"""
import glob
import json
import math
import os

BATCHES = ["/tmp/evobot-pair16", "/tmp/evobot-pair32"]
VERSIONS = [("v1", "self_assessment_v1.json", "plan labelled 'executed'"),
            ("v2", "self_assessment_v2.json", "measurably over-corrected"),
            ("v3", "self_assessment_v3.json", "intent labelled, no blanket distrust"),
            ("v4", "self_assessment_v4.json", "v3 + robot frame stated")]


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
            doc = json.load(open(v, encoding="utf-8"))
            rec = {"id": os.path.basename(d), "passed": bool(doc.get("passed"))}
            for key, fname, _ in VERSIONS:
                p = os.path.join(d, fname)
                rec[key] = None
                if os.path.exists(p):
                    try:
                        rec[key] = bool(json.load(open(p, encoding="utf-8"))["success"])
                    except Exception:
                        pass
            rows.append(rec)

    print("%-6s %-40s %6s %8s %8s %10s" % (
        "ver", "prompt", "n", "false+", "false-", "accuracy"))
    summary = {}
    for key, fname, label in VERSIONS:
        have = [r for r in rows if r[key] is not None]
        fs = sum(1 for r in have if r[key] and not r["passed"])
        ff = sum(1 for r in have if (not r[key]) and r["passed"])
        acc = sum(1 for r in have if r[key] == r["passed"])
        summary[key] = (fs, ff, acc, len(have))
        print("%-6s %-40s %6d %8d %8d %6d/%-3d" % (
            key, label, len(have), fs, ff, acc, len(have)))
    print()
    for key, fname, label in VERSIONS:
        fs, ff, acc, n = summary[key]
        for name, k in (("false success", fs), ("false failure", ff), ("accuracy", acc)):
            p, lo, hi = wilson(k, n)
            print("%-3s %-14s %2d/%-2d = %5.1f%% (%.1f-%.1f%%)" % (
                key, name, k, n, 100 * p, 100 * lo, 100 * hi))
        print()

    fs3 = summary["v3"][0]
    print("MISSION REQUIREMENT (false success must be 0):")
    print("  v3 = %d/%d -> %s" % (fs3, summary["v3"][3],
                                    "MET" if fs3 == 0 else "NOT MET"))
    print()
    print("BUT: a zero obtained by pessimism is not a fix. v3 must also keep accuracy")
    print("above v2; v2's accuracy drop is why it was rejected as the answer.")
    print("  v2 accuracy %d/%d, v3 accuracy %d/%d" % (
        summary["v2"][2], summary["v2"][3], summary["v3"][2], summary["v3"][3]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
