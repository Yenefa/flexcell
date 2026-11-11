#!/usr/bin/env python3
"""Compare two validated batches to decide whether capability GENERALIZES.

WHY THIS IS NOT JUST "RUN IT AGAIN": repeating the same instances only re-measures the same
world. Generalization means the capability holds on task instances that no run in this
project has ever touched. The second batch uses seeds 8100/8200, generated after every
earlier batch and checked for zero overlap with public16/32/48.

The honest question is not "is batch 2 good" but "does it look like batch 1". If the rates
differ by more than the intervals can explain, the capability is instance-specific and the
generalization rung is NOT earned, whatever the individual numbers are.
"""
import json
import math
import os
import subprocess
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def read(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def score(base):
    import glob
    rows = []
    for d in sorted(glob.glob(os.path.join(base, "HO-*"))):
        b = read(os.path.join(d, "verdict_after1.json")) or {}
        r = read(os.path.join(d, "verdict.json")) or {}
        obs_p = os.path.join(d, "observation_claimed.json")
        if not os.path.exists(obs_p):
            obs_p = os.path.join(d, "observation.json")
        obs = read(obs_p) or {}
        rows.append({
            "id": os.path.basename(d),
            "b": bool(b.get("passed")),
            "r": bool(r.get("passed")),
            "false_success": bool(r.get("false_success")),
            "measured": obs.get("agent_claim_source") == "measured",
            "retried": os.path.exists(os.path.join(d, "plan_retry.json")),
        })
    return rows


def main():
    v = os.path.join(WT, "experiments", "baselines", "validate_batch.py")
    out = {}
    for label, base in (("batch1_seeds7500", "/tmp/evobot-batch1"),
                        ("batch2_seeds8100", "/tmp/evobot-batch2")):
        if not os.path.isdir(base):
            print("%s: MISSING" % label)
            return 1
        rc = subprocess.run([sys.executable, v, base], capture_output=True, text=True)
        print("%s validation rc=%d" % (label, rc.returncode))
        if rc.returncode != 0:
            print(rc.stdout.strip()[:600])
            print("REFUSING: an unvalidated batch cannot support a generalization claim.")
            return 1
        out[label] = score(base)

    print()
    print("%-18s %-8s %-8s %-8s %-8s %s" % ("batch", "n", "B", "R", "retried",
                                             "false_success"))
    stats = {}
    for label, rows in out.items():
        n = len(rows)
        b = sum(1 for x in rows if x["b"])
        r = sum(1 for x in rows if x["r"])
        ret = sum(1 for x in rows if x["retried"])
        fsr = sum(1 for x in rows if x["false_success"])
        stats[label] = (n, b, r, ret, fsr)
        print("%-18s %-8d %-8s %-8s %-8d %d" % (
            label, n, "%d/%d" % (b, n), "%d/%d" % (r, n), ret, fsr))

    print()
    b1, b2 = stats["batch1_seeds7500"], stats["batch2_seeds8100"]
    for idx, arm in ((1, "B (first try)"), (2, "R (final)")):
        k1, n1 = b1[idx], b1[0]
        k2, n2 = b2[idx], b2[0]
        p1, lo1, hi1 = wilson(k1, n1)
        p2, lo2, hi2 = wilson(k2, n2)
        # pooled rate across both sets
        pp, lop, hip = wilson(k1 + k2, n1 + n2)
        # do the intervals overlap? if not, the two sets disagree beyond noise
        overlap = not (hi2 < lo1 or hi1 < lo2)
        print("arm %s" % arm)
        print("  seeds 7500: %d/%d = %.1f%% (%.1f-%.1f%%)" % (
            k1, n1, 100 * p1, 100 * lo1, 100 * hi1))
        print("  seeds 8100: %d/%d = %.1f%% (%.1f-%.1f%%)" % (
            k2, n2, 100 * p2, 100 * lo2, 100 * hi2))
        print("  pooled    : %d/%d = %.1f%% (%.1f-%.1f%%)" % (
            k1 + k2, n1 + n2, 100 * pp, 100 * lop, 100 * hip))
        print("  intervals overlap: %s" % ("YES" if overlap else "NO - sets DISAGREE"))
        print()

    print("VERDICT INPUTS, not a verdict:")
    print("  A generalization claim needs the new set to be consistent with the old one.")
    print("  Consistency is necessary, not sufficient: two sets agreeing on 16 instances")
    print("  each still bounds the true rate only to the pooled interval above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
