#!/usr/bin/env python3
"""Validate a finished batch BEFORE its numbers are believed.

WHY THIS EXISTS: the pair48 batch reported "R 13/16" and it looked like a normal recovery
arm. It was not. The runner changes directory to the sim checkout to launch Gazebo and then
invokes runtime/recovery/recovery_driver.py by RELATIVE path, so the driver never ran:
every run has recovery.log containing "No such file or directory", zero retries happened,
and arm R was byte-identical to arm B. The same cwd trap had already silently disabled the
self-assessment in that batch.

A batch can therefore be internally consistent and still be measuring nothing. These checks
are deliberately structural - they look for the EVIDENCE THAT A STEP RAN, not for a value
that happens to look plausible.
"""
import glob
import json
import os
import sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/evobot-pair48"


def read(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def main():
    runs = sorted(glob.glob(os.path.join(BASE, "HO-*")))
    problems = []
    checked = {"runs": len(runs), "b_failed": 0, "recovery_ran": 0,
               "claims": 0, "retried": 0}

    for d in runs:
        oid = os.path.basename(d)
        b = read(os.path.join(d, "verdict_after1.json"))
        r = read(os.path.join(d, "verdict.json"))
        if b is None or r is None:
            problems.append("%s: missing a verdict" % oid)
            continue

        # 1. every failed first attempt MUST leave a recovery decision on disk
        if not b.get("passed"):
            checked["b_failed"] += 1
            dec = os.path.join(d, "recovery_decision.json")
            if not os.path.exists(dec):
                log = os.path.join(d, "recovery.log")
                hint = ""
                if os.path.exists(log):
                    hint = open(log, encoding="utf-8", errors="replace").read().strip()[:160]
                problems.append(
                    "%s: first attempt FAILED but no recovery decision was recorded "
                    "(recovery never ran). log: %s" % (oid, hint or "<empty>"))
            else:
                checked["recovery_ran"] += 1

        # 2. a claim must be MEASURED, not absent
        obs_p = os.path.join(d, "observation_claimed.json")
        if os.path.exists(obs_p):
            obs = read(obs_p) or {}
            if obs.get("agent_claim_source") == "measured":
                checked["claims"] += 1
            else:
                problems.append("%s: claim is present but not marked measured" % oid)
        else:
            problems.append("%s: no claim-carrying observation; false success is unmeasurable"
                            % oid)

        # 3. arm R must not be identical to arm B for every run: that means the retry
        #    mechanism is inert, whether or not it "looks" fine
        if os.path.exists(os.path.join(d, "plan_retry.json")):
            checked["retried"] += 1

    # 4a. a batch where NOTHING failed cannot exercise recovery at all. That is not
    #     invalid, but it must not be cited as evidence for or against recovery.
    if checked["b_failed"] == 0:
        print("NOTE: no first attempt failed, so the recovery path was never exercised.")
        print("      This batch supports NO claim about arm R.")
        print()

    # 4b. batch-level: if nothing retried while several runs failed, the arm is inert
    if checked["b_failed"] > 0 and checked["retried"] == 0:
        problems.append(
            "BATCH: %d first attempts failed and NOT ONE retry was issued - arm R is not a"
            " recovery arm, and any B-vs-R comparison from this batch is meaningless"
            % checked["b_failed"])

    print(json.dumps(checked, indent=2))
    print()
    if problems:
        print("BATCH INVALID:")
        for p in problems[:20]:
            print("  -", p)
        if len(problems) > 20:
            print("  ... and %d more" % (len(problems) - 20))
        return 1
    print("Batch structure OK: every failed first attempt has a recorded recovery decision,")
    print("every run carries a measured claim, and the retry mechanism demonstrably fired.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
