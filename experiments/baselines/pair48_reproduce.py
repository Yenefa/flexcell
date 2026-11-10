#!/usr/bin/env python3
"""Compare the ORIGINAL pair48 batch with the re-run of the instances that failed in it.

WHY: pair48 reported 3 first-attempt failures and an arm R that was byte-identical to arm B,
because recovery never ran. Re-running those exact 3 instances with the SAME plan and the
cwd fixed gave 3 first-attempt passes. So the failures did not reproduce - which is the same
transient behaviour seen earlier when identical coordinates both succeeded and stalled.

Reporting "B 13/16" alone would hide that. Reporting "R 14/16" would be worse: it would
attribute to recovery a pass that recovery never touched.
"""
import glob
import json
import os
import sys

ORIG = "/tmp/evobot-pair48"
RERUN = "/tmp/evobot-pair48b"
FAILED = ["HO-38ce6531a597", "HO-4f197a0997af", "HO-72553754ef3a"]


def read(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def main():
    orig_runs = sorted(glob.glob(os.path.join(ORIG, "HO-*")))
    b_pass = r_pass = 0
    for d in orig_runs:
        b = read(os.path.join(d, "verdict_after1.json")) or {}
        r = read(os.path.join(d, "verdict.json")) or {}
        b_pass += 1 if b.get("passed") else 0
        r_pass += 1 if r.get("passed") else 0
    n = len(orig_runs)

    print("ORIGINAL batch (recovery never ran):")
    print("  B pass: %d/%d" % (b_pass, n))
    print("  R pass: %d/%d  <- IDENTICAL to B; arm R is NOT a recovery arm" % (r_pass, n))
    print()

    print("RE-RUN of the %d instances that failed (same plan, cwd fixed):" % len(FAILED))
    reproduced = 0
    for oid in FAILED:
        d = os.path.join(RERUN, oid)
        if not os.path.isdir(d):
            print("  %-20s MISSING" % oid)
            continue
        b = read(os.path.join(d, "verdict_after1.json")) or {}
        r = read(os.path.join(d, "verdict.json")) or {}
        dec = read(os.path.join(d, "recovery_decision.json")) or {}
        action = (dec.get("decision") or dec).get("action")
        print("  %-20s B=%-6s R=%-6s action=%s" % (oid, b.get("passed"),
                                                   r.get("passed"), action))
        if not b.get("passed"):
            reproduced += 1
    print()
    print("  failures that REPRODUCED: %d/%d" % (reproduced, len(FAILED)))
    print()
    if reproduced == 0:
        print("CONCLUSION: the original 3 failures were TRANSIENT. They did not reproduce on")
        print("a re-run with an identical plan, and all 3 passed on the first attempt, so")
        print("recovery was never needed. Any 'B vs R' comparison from the original batch is")
        print("void: recovery never executed, and on re-run there was nothing to recover.")
        print()
        print("This also means the original B=13/16 is ONE SAMPLE of a noisy process, not a")
        print("property of the instances.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
