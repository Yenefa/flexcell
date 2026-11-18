#!/usr/bin/env python3
"""Resolve live experience parameters into a FILE the runtime may read as plain data.

WHY THIS EXISTS: ADR-002 and config/skill_boundaries.json forbid the execution layer
(runtime/) from importing the development layer (evolution/). The live wiring used to make
recovery_driver.py import live_binding directly -- a real architecture violation that CI
exposed once the entry-id churn was fixed. This script runs on the DEVELOPMENT side, imports
the experience package freely, and writes the resolved kwargs + audit reason as DATA. The
runtime reads that file with no import from evolution: a one-way flow, as the ADR requires.

The gate semantics are unchanged: chain intact, ACTIVE+latest, independent ACCEPT bound to
entry_id and entry chain hash, numeric kwargs from the entry, applicability on the real plan.
Any gate failure writes an EMPTY kwargs dict (a refusal), never a crash.
"""
import argparse
import json
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import live_binding  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", required=True)
    ap.add_argument("--entries", required=True)
    ap.add_argument("--consumer", default="executor_recovery")
    ap.add_argument("--review-ledger")
    ap.add_argument("--observation", help="path to the real plan.json")
    ap.add_argument("--out", required=True, help="where to write the binding JSON")
    args = ap.parse_args(argv)
    observation = None
    if args.observation:
        try:
            observation = {"plan": json.load(open(args.observation, encoding="utf-8"))}
        except (OSError, ValueError) as exc:
            observation = {"_unreadable": str(exc)}
    try:
        kwargs, why = live_binding.resolve(
            args.asset, args.consumer, args.entries,
            review_ledger=args.review_ledger, observation=observation)
    except Exception as exc:  # noqa: BLE001 - a binding failure is a refusal
        kwargs, why = {}, "binding failed: %s" % exc
    payload = {"consumer": args.consumer, "kwargs": kwargs, "why": why,
               "note": "resolved by the development side; runtime reads this as data"}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
