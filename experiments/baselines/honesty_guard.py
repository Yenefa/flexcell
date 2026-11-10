#!/usr/bin/env python3
"""Refuse to report a false-success rate that was never actually measured.

WHY THIS EXISTS: for many rounds I reported "False Success Rate 0/32". It was vacuous.
Two independent harness defects combined to guarantee the zero:

  1. observe_from_run.build_observation defaults agent_claimed_success to False, and
     evaluate() computes claimed = bool(final_state.get(...)), so a missing claim becomes
     False and a false success is structurally impossible;
  2. the runner never invoked runtime/verifier/self_assess.py at all, and when it was
     invoked with the default 2048-token budget the reasoning model returned EMPTY
     content for this prompt, which parses as "no JSON" and again leaves the default.

Measured, honest numbers after collecting 30 of 32 self-assessments: false success
1/30 (3.3%), false failure 10/30 (33.3%), self-assessment accuracy 19/30 (63.3%).

This module makes the failure mode loud: a rate is only reportable when every run carries
a claim, and a zero is only accepted when it is a real zero.
"""
import glob
import json
import os
import sys

BATCHES = ["/tmp/evobot-pair16", "/tmp/evobot-pair32"]

# The CURRENT authoritative assessment, newest first. The earlier versions are kept on
# disk as evidence of the v1 defect and of the rejected v2/v3 prompts, so the guard must
# name the version it used instead of silently picking one.
ASSESSMENT_FILES = ["self_assessment_v4.json", "self_assessment_v3.json",
                    "self_assessment_v2.json", "self_assessment_v1.json",
                    "self_assessment.json"]


def collect(batches=None):
    rows = []
    for base in (batches or BATCHES):
        for d in sorted(glob.glob(os.path.join(base, "HO-*"))):
            v = os.path.join(d, "verdict.json")
            if not os.path.exists(v):
                continue
            doc = json.load(open(v, encoding="utf-8"))
            claim = None
            used = None
            for name in ASSESSMENT_FILES:
                s = os.path.join(d, name)
                if not os.path.exists(s):
                    continue
                try:
                    claim = bool(json.load(open(s, encoding="utf-8")).get("success"))
                    used = name
                except Exception:
                    claim = None
                break
            rows.append({"id": os.path.basename(d), "claim": claim,
                         "passed": bool(doc.get("passed")), "assessment": used})
    return rows


def false_success_report(rows, require_complete=True):
    """Return (ok_to_report, payload). ok_to_report is False when the number is vacuous."""
    n = len(rows)
    have = [r for r in rows if r["claim"] is not None]
    missing = n - len(have)
    fs = sum(1 for r in have if r["claim"] and not r["passed"])
    ff = sum(1 for r in have if (not r["claim"]) and r["passed"])
    versions = sorted({r.get("assessment") for r in have if r.get("assessment")})
    payload = {"runs": n, "with_claim": len(have), "missing_claim": missing,
               "assessment_version": versions,
               "false_success": fs, "false_failure": ff}
    if missing:
        payload["why_not_reportable"] = (
            "%d run(s) carry no agent claim, so their zero is vacuous: evaluate() treats "
            "a missing claim as False and a false success then cannot occur" % missing)
        return (not require_complete), payload
    return True, payload


def main():
    rows = collect()
    ok, payload = false_success_report(rows)
    print(json.dumps(payload, indent=2))
    print()
    if not ok:
        print("REFUSING to report a false-success RATE: the measurement is incomplete.")
        print("Collect the missing self-assessments (runtime/verifier/fill_self_assess.py)")
        print("before quoting any zero.")
        return 1
    print("Every run carries an agent claim; the rate above is measured, not assumed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
