#!/usr/bin/env python3
"""Report a batch only after it passes structural validation, and only with intervals.

WHY THE VALIDATION COMES FIRST: two earlier batches produced plausible numbers while a
pipeline step had silently not run - one had no claims at all, the other had "arm R" that
was arm B relabelled. A number from an unvalidated batch is not a weaker result, it is not a
result. So this refuses to print anything until validate_batch.py exits 0.

The paired comparison is reported as gained/lost rather than as two independent rates,
because the same instances are run in both arms - two separate Wilson intervals would hide
that the arms are correlated.
"""
import glob
import json
import math
import os
import subprocess
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/evobot-batch1"


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


def main():
    v = os.path.join(WT, "experiments", "baselines", "validate_batch.py")
    rc = subprocess.run([sys.executable, v, BASE], capture_output=True, text=True)
    print(rc.stdout.strip())
    print()
    if rc.returncode != 0:
        print("REFUSING to report metrics: the batch failed structural validation.")
        print("Any number computed from it would be a number about a pipeline that did not run.")
        return 1

    runs = sorted(glob.glob(os.path.join(BASE, "HO-*")))
    rows = []
    for d in runs:
        b = read(os.path.join(d, "verdict_after1.json")) or {}
        r = read(os.path.join(d, "verdict.json")) or {}
        obs_p = os.path.join(d, "observation_claimed.json")
        if not os.path.exists(obs_p):
            obs_p = os.path.join(d, "observation.json")
        obs = read(obs_p) or {}
        dec = read(os.path.join(d, "recovery_decision.json")) or {}
        rows.append({
            "id": os.path.basename(d),
            "b": bool(b.get("passed")),
            "r": bool(r.get("passed")),
            "claim": (r.get("agent_claimed_success")
                      if obs.get("agent_claim_source") == "measured" else None),
            "false_success": bool(r.get("false_success")),
            "false_failure": bool(r.get("false_failure")),
            "retried": os.path.exists(os.path.join(d, "plan_retry.json")),
            "action": (dec.get("decision") or dec).get("action"),
        })

    n = len(rows)
    measured = [x for x in rows if x["claim"] is not None]
    nm = len(measured)
    b_pass = sum(1 for x in rows if x["b"])
    r_pass = sum(1 for x in rows if x["r"])
    gained = [x["id"] for x in rows if not x["b"] and x["r"]]
    lost = [x["id"] for x in rows if x["b"] and not x["r"]]
    fs = sum(1 for x in measured if x["false_success"])
    ff = sum(1 for x in measured if x["false_failure"])
    acc = sum(1 for x in measured if x["claim"] == x["r"])

    print("%-20s %-6s %-6s %-8s %-7s %s" % ("run", "B", "R", "claim",
                                            "retry", "flags"))
    for x in rows:
        flags = []
        if x["false_success"]:
            flags.append("FALSE_SUCCESS")
        if x["false_failure"]:
            flags.append("false_failure")
        print("%-20s %-6s %-6s %-8s %-7s %s" % (x["id"], x["b"], x["r"],
                                                x["claim"], x["retried"],
                                                ",".join(flags)))
    print()
    pb, lob, hib = wilson(b_pass, n)
    pr, lor, hir = wilson(r_pass, n)
    print("instances        : %d" % n)
    print("arm B (first try): %d/%d = %.1f%% (%.1f-%.1f%%)" % (
        b_pass, n, 100 * pb, 100 * lob, 100 * hib))
    print("arm R (final)    : %d/%d = %.1f%% (%.1f-%.1f%%)" % (
        r_pass, n, 100 * pr, 100 * lor, 100 * hir))
    print("paired           : gained %d %s | lost %d %s" % (
        len(gained), gained or "", len(lost), lost or ""))
    print("retries issued   : %d" % sum(1 for x in rows if x["retried"]))
    print()
    if nm == 0:
        print("REFUSING to report honesty rates: no run has a measured claim.")
        return 1
    for label, k in (("FALSE SUCCESS", fs), ("FALSE FAILURE", ff),
                     ("ASSESS ACCURACY", acc)):
        p, lo, hi = wilson(k, nm)
        print("%-16s %2d/%-2d = %5.1f%% (%.1f-%.1f%%)" % (label, k, nm,
                                                          100 * p, 100 * lo, 100 * hi))
    print()
    if len(gained) == 0 and len(lost) == 0 and r_pass == b_pass:
        print("NOTE: arm R equals arm B on every instance. Either recovery was never")
        print("      needed, or it is still inert - check 'retries issued' above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
