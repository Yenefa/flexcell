#!/usr/bin/env python3
"""Two ways for the agent to answer "did I succeed?", scored against the evaluator.

WHY: false success is the mission's cardinal sin, but its mirror - claiming failure while the
world is fine - was measured at 5/48 and is what makes recovery retry finished work. The agent
currently answers the question with an LLM self-assessment. This compares that answer against a
DETERMINISTIC one built from the same measurements, and scores both against the evaluator.

WHAT THE DETERMINISTIC CHECK MAY USE: only the plan's own declared tolerance and the measured
object positions - the same inputs the recovery layer already uses. It never reads the
evaluator's acceptance radius or the sealed answer, so a high score cannot come from peeking.
Its coverage is honestly partial: it refuses when an object appears in more than one plan stage,
because then the goal includes an ordering that positions cannot prove.
"""
import glob
import json
import math
import os
import sys

WT = "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp"
sys.path.insert(0, os.path.join(WT, "runtime", "recovery"))
import goal_check as GC

BATCHES = ["/tmp/evobot-batch1", "/tmp/evobot-batch2",
           "/tmp/evobot-batch3", "/tmp/evobot-batch4"]


def read(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def main():
    rows = []
    for base in BATCHES:
        for d in sorted(glob.glob(os.path.join(base, "HO-*"))):
            oid = os.path.basename(d)
            verdict = read(os.path.join(d, "verdict.json"))
            if not verdict:
                continue
            plan = read(os.path.join(d, "plan.json")) or {}
            gt = read(os.path.join(d, "ground_truth.json")) or {}
            sa = read(os.path.join(d, "self_assessment.json")) or {}
            obs = read(os.path.join(d, "observation_claimed.json")) or \
                read(os.path.join(d, "observation.json")) or {}

            llm_claim = sa.get("success")
            measured = obs.get("agent_claim_source") == "measured"

            sat, detail = GC.check(plan, gt.get("objects") or {})
            if "repeated_objects" in detail or "why" in detail:
                det_claim = None          # refused: cannot conclude
            else:
                det_claim = bool(sat)

            passed = bool(verdict.get("passed"))
            rows.append({"id": oid, "passed": passed, "llm": llm_claim,
                         "det": det_claim, "measured": measured,
                         "det_note": detail.get("why", "")})

    n = len(rows)
    print("runs:", n)
    print()
    llm_cov = [r for r in rows if r["llm"] is not None]
    det_cov = [r for r in rows if r["det"] is not None]
    for label, sub, key in (("LLM self-assessment", llm_cov, "llm"),
                            ("deterministic measurement check", det_cov, "det")):
        if not sub:
            print("%-32s no coverage" % label)
            continue
        wrong = [r for r in sub if r[key] != r["passed"]]
        print("%-32s coverage %2d/%d  correct %2d  WRONG %2d  accuracy %.1f%%" % (
            label, len(sub), n, len(sub) - len(wrong), len(wrong),
            100.0 * (len(sub) - len(wrong)) / len(sub)))
        for r in wrong:
            print("     wrong: %s passed=%s claim=%s" % (r["id"], r["passed"], r[key]))
    print()
    both = [r for r in rows if r["llm"] is not None and r["det"] is not None]
    if both:
        agree = sum(1 for r in both if bool(r["llm"]) == bool(r["det"]))
        print("on the %d runs both can answer: agree %d, disagree %d" % (
            len(both), agree, len(both) - agree))
        for r in both:
            if bool(r["llm"]) != bool(r["det"]):
                print("     disagree: %s passed=%s llm=%s det=%s" % (
                    r["id"], r["passed"], r["llm"], r["det"]))
    print()
    print("READING: whichever is more accurate is the one the agent should use for its claim.")
    print("The deterministic check has lower coverage by construction - it declines where a")
    print("sequence matters - so a high accuracy on a small subset is not automatically better.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
