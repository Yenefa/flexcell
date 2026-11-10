#!/usr/bin/env python3
"""Compare the v1 and v2 self-assessments against independent ground truth.

WHY BOTH VERSIONS MATTER: v1 is the evidence of the defect (a plan mistaken for
execution). v2 is the corrected prompt. Keeping only v2 would erase the evidence, and
comparing them shows whether the fix actually changed behaviour rather than just wording.
"""
import glob
import json
import math
import os

BATCHES = ["/tmp/evobot-pair16", "/tmp/evobot-pair32"]


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def load(d, name):
    p = os.path.join(d, name)
    if not os.path.exists(p):
        return None
    try:
        return bool(json.load(open(p, encoding="utf-8")).get("success"))
    except Exception:
        return None


def score(rows, key):
    have = [r for r in rows if r[key] is not None]
    fs = [r for r in have if r[key] and not r["passed"]]
    ff = [r for r in have if (not r[key]) and r["passed"]]
    acc = [r for r in have if r[key] == r["passed"]]
    return have, fs, ff, acc


def main():
    rows = []
    for base in BATCHES:
        for d in sorted(glob.glob(os.path.join(base, "HO-*"))):
            v = os.path.join(d, "verdict.json")
            if not os.path.exists(v):
                continue
            doc = json.load(open(v, encoding="utf-8"))
            rows.append({"id": os.path.basename(d), "passed": bool(doc.get("passed")),
                         "v1": load(d, "self_assessment_v1.json"),
                         "v2": load(d, "self_assessment_v2.json")})
    n = len(rows)
    print("runs:", n)
    print()
    print("%-14s %8s %8s %8s %8s" % ("version", "claimed", "false+", "false-", "accuracy"))
    for key, label in (("v1", "v1 (plan-as-")  , ("v2", "v2 (corrected)")):
        pass
    for key, label in (("v1", "v1 plan-as-exec"), ("v2", "v2 corrected")):
        have, fs, ff, acc = score(rows, key)
        if not have:
            print("%-14s no data" % label)
            continue
        print("%-14s %8d %8d %8d %8d/%d" % (label,
              sum(1 for r in have if r[key]), len(fs), len(ff), len(acc), len(have)))
        if key == "v1":
            v1_fs = len(fs)
            v1_ff = len(ff)
            v1_acc = len(acc)
            v1_n = len(have)
        else:
            v2_fs = len(fs)
            v2_ff = len(ff)
            v2_acc = len(acc)
            v2_n = len(have)
    print()
    for label, k, nn in (("v1 false success", v1_fs, v1_n),
                         ("v2 false success", v2_fs, v2_n),
                         ("v1 false failure", v1_ff, v1_n),
                         ("v2 false failure", v2_ff, v2_n),
                         ("v1 accuracy", v1_acc, v1_n),
                         ("v2 accuracy", v2_acc, v2_n)):
        p, lo, hi = wilson(k, nn)
        print("%-20s %d/%d = %.1f%% (%.1f-%.1f%%)" % (label, k, nn, 100 * p,
                                                       100 * lo, 100 * hi))
    print()
    changed = [r for r in rows if r["v1"] is not None and r["v2"] is not None
               and r["v1"] != r["v2"]]
    print("verdicts that CHANGED between v1 and v2:", len(changed))
    for r in changed[:10]:
        print("  %-20s v1=%-5s v2=%-5s passed=%s" % (r["id"], r["v1"], r["v2"], r["passed"]))
    print()
    print("MISSION REQUIREMENT: false success must be 0.")
    print("v2 measured: %d/%d -> %s" % (v2_fs, v2_n,
                                        "MET" if v2_fs == 0 else "STILL NOT MET"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
