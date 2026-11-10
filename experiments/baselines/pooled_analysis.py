#!/usr/bin/env python3
"""Pool both 16-instance batches and report intervals, not just point estimates.

WHY: 4/16 stalls and 3/4 recovered were reported as single numbers. A point estimate from
n=16 invites over-reading: 25% has a 95% interval spanning roughly 7%-52%. Pooling fresh
seeds doubles n and, more importantly, lets the interval be stated honestly.

Wilson intervals are used because they behave sensibly at small n and near 0 or 1, unlike
the normal approximation.
"""
import glob
import json
import math
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "runtime", "recovery"))
import execution_root_cause as E

BATCHES = [("batch1", "/tmp/evobot-pair16"), ("batch2", "/tmp/evobot-pair32")]


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d
    return p, max(0.0, centre - half), min(1.0, centre + half)


def load(base):
    rows = []
    for d in sorted(glob.glob(os.path.join(base, "HO-*"))):
        oid = os.path.basename(d)
        b = os.path.join(d, "verdict_after1.json")
        r = os.path.join(d, "verdict.json")
        if not (os.path.exists(b) and os.path.exists(r)):
            continue
        try:
            bd = json.load(open(b, encoding="utf-8"))
            rd = json.load(open(r, encoding="utf-8"))
        except Exception:
            continue
        label, _ = E.run_root_cause(d)
        rows.append({"id": oid, "b": bool(bd.get("passed")), "r": bool(rd.get("passed")),
                     "cause": label, "false_success": bool(bd.get("false_success")
                                                        or rd.get("false_success"))})
    return rows


def report(rows, name):
    n = len(rows)
    if not n:
        print("%-8s no data" % name)
        return
    b = sum(1 for r in rows if r["b"])
    r_ = sum(1 for r in rows if r["r"])
    # A stall can occur and still be absorbed: the composite retried the stage inside
    # the same run (3 episodes: FAIL then OK then OK), so "stall seen" is NOT the same as
    # "stall caused the failure". Both numbers are reported separately.
    stalls = [x for x in rows if x["cause"] == "ACTUATOR_STALL_ON_RELEASE"]
    st = len(stalls)
    st_failed = sum(1 for x in stalls if not x["b"])
    st_absorbed = st - st_failed
    rec = sum(1 for x in stalls if x["r"] and not x["b"])
    still = sum(1 for x in stalls if not x["r"])
    fs = sum(1 for x in rows if x["false_success"])
    pb, lb, ub = wilson(b, n)
    pr, lr, ur = wilson(r_, n)
    ps, ls, us = wilson(st, n)
    print("%-8s n=%-3d B=%d/%d (%.0f%%, %.0f-%.0f%%)  R=%d/%d (%.0f%%, %.0f-%.0f%%)"
          % (name, n, b, n, 100 * pb, 100 * lb, 100 * ub,
             r_, n, 100 * pr, 100 * lr, 100 * ur))
    print("%-8s stalls seen=%d/%d (%.0f%%, %.0f-%.0f%%)  absorbed_in_run=%d  "
          "caused_failure=%d  recovered_by_retry=%d  still_failing=%d  false_success=%d"
          % ("", st, n, 100 * ps, 100 * ls, 100 * us, st_absorbed, st_failed, rec, still, fs))


def main():
    allrows = []
    for name, base in BATCHES:
        rows = load(base)
        report(rows, name)
        allrows.extend(rows)
    print()
    report(allrows, "POOLED")
    n = len(allrows)
    if n:
        b = sum(1 for r in allrows if r["b"])
        r_ = sum(1 for r in allrows if r["r"])
        gained = sum(1 for r in allrows if r["r"] and not r["b"])
        lost = sum(1 for r in allrows if r["b"] and not r["r"])
        fs = sum(1 for r in allrows if r["false_success"])
        print()
        print("paired transitions: gained=%d lost=%d" % (gained, lost))
        print("FALSE SUCCESS RATE: %d/%d = %.1f%%" % (fs, n, 100.0 * fs / n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
