#!/usr/bin/env python3
"""Validate a finished batch BEFORE its numbers are believed.

WHY THIS EXISTS: the pair48 batch reported "R 13/16" and it looked like a normal recovery
arm. It was not. The runner changed directory to the sim checkout and then invoked
recovery_driver.py by RELATIVE path, so the driver never ran: every run logged "No such file
or directory", zero retries happened, and arm R was byte-identical to arm B. The same cwd
trap had already silently disabled the self-assessment.

A batch can be internally consistent and still measure nothing, so these checks look for
EVIDENCE THAT A STEP RAN, not for a value that happens to look plausible.

Two outcomes are distinguished:
  INVALID  - a required step did not run, or a claim was not measured. No number from the
             batch may be reported at all.
  ANOMALY  - the data is sound but something surprising is recorded that a reader must see,
             e.g. a retry issued although the first attempt already passed, which means the
             skill layer disagreed with the measured world.
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
    invalid = []
    anomalies = []
    checked = {"runs": len(runs), "b_failed": 0, "recovery_ran": 0, "claims": 0,
               "retried": 0, "retried_after_pass": 0}

    for d in runs:
        oid = os.path.basename(d)
        b = read(os.path.join(d, "verdict_after1.json"))
        r = read(os.path.join(d, "verdict.json"))
        if b is None or r is None:
            invalid.append("%s: missing a verdict" % oid)
            continue

        b_passed = bool(b.get("passed"))

        # 1. every failed first attempt MUST leave a recovery decision on disk
        if not b_passed:
            checked["b_failed"] += 1
            if not os.path.exists(os.path.join(d, "recovery_decision.json")):
                log = os.path.join(d, "recovery.log")
                hint = ""
                if os.path.exists(log):
                    hint = open(log, encoding="utf-8", errors="replace").read().strip()[:160]
                invalid.append(
                    "%s: first attempt FAILED but no recovery decision was recorded "
                    "(recovery never ran). log: %s" % (oid, hint or "<empty>"))

        # 2. did recovery actually execute? counted whenever a decision exists, whether or
        #    not the first attempt failed. Counting it only on failure hid the fact that
        #    recovery ran on a batch where nothing failed.
        if os.path.exists(os.path.join(d, "recovery_decision.json")):
            checked["recovery_ran"] += 1

        # 3. a claim must be MEASURED, not absent
        obs_p = os.path.join(d, "observation_claimed.json")
        if os.path.exists(obs_p):
            obs = read(obs_p) or {}
            if obs.get("agent_claim_source") == "measured":
                checked["claims"] += 1
            else:
                invalid.append("%s: claim present but not marked measured" % oid)
        else:
            invalid.append(
                "%s: no claim-carrying observation; false success is unmeasurable" % oid)

        # 4. a retry despite a PASSING first attempt means the skill layer reported a
        #    failure that the measured world contradicts. The data stays sound - the
        #    verdict and the claim are unaffected - but it must be surfaced, because it
        #    inflates the retry count and makes arm R look exercised when it was not needed.
        retried = os.path.exists(os.path.join(d, "plan_retry.json"))
        if retried:
            checked["retried"] += 1
            if b_passed:
                checked["retried_after_pass"] += 1
                dec = read(os.path.join(d, "recovery_decision.json")) or {}
                dec = dec.get("decision") or dec
                anomalies.append(
                    "%s: SKILL_LAYER_DISAGREEMENT - first attempt PASSED but a retry was "
                    "issued (action=%s, class=%s, reason=%r)" % (
                        oid, dec.get("action"), dec.get("failure_class"),
                        (dec.get("measured_reason") or "")[:90]))

    # 5. a batch where NOTHING failed cannot exercise recovery as a fix
    if checked["b_failed"] == 0:
        anomalies.append(
            "no first attempt failed: recovery was never needed, so this batch supports "
            "no claim about recovery EFFICACY")

    # 6. failures present but no retry at all means the arm is inert
    if checked["b_failed"] > 0 and checked["retried"] == 0:
        invalid.append(
            "BATCH: %d first attempts failed and NOT ONE retry was issued - arm R is not a"
            " recovery arm, and any B-vs-R comparison from this batch is meaningless"
            % checked["b_failed"])

    print(json.dumps(checked, indent=2))
    print()
    if anomalies:
        print("ANOMALIES (data sound, but a reader must see these):")
        for a in anomalies[:20]:
            print("  -", a)
        if len(anomalies) > 20:
            print("  ... and %d more" % (len(anomalies) - 20))
        print()
    if invalid:
        print("BATCH INVALID:")
        for p in invalid[:20]:
            print("  -", p)
        if len(invalid) > 20:
            print("  ... and %d more" % (len(invalid) - 20))
        return 1
    print("Batch structure OK: every failed first attempt has a recorded recovery decision,")
    print("every run carries a measured claim, and the retry mechanism demonstrably fired.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
