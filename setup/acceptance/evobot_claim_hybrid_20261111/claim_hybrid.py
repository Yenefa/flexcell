#!/usr/bin/env python3
"""Score the two-condition claim, the LLM claim, and a hybrid, against the evaluator.

THE HYBRID RULE IS PRINCIPLED, NOT FITTED: use the deterministic check where it can conclude,
because it measures execution directly; otherwise fall back to the self-assessment, which reads
the instruction and can notice a plan that does not match it. Each component answers the question
it is suited to. The 100%-style figures below are IN-SAMPLE and must be tested on a new batch
before anything is adopted.
"""
import glob
import json
import os
import sys

WT = "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp"
sys.path.insert(0, os.path.join(WT, "runtime", "verifier"))
import claim as C

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
            obs = read(os.path.join(d, "observation_input.json")) or {}
            sa = read(os.path.join(d, "self_assessment.json")) or {}
            det, detail = C.check(plan, gt.get("objects") or {}, obs.get("zones") or [])
            llm = sa.get("success")
            passed = bool(verdict.get("passed"))
            hybrid = det if det is not None else llm
            rows.append({"id": oid, "passed": passed, "det": det, "llm": llm,
                         "hybrid": hybrid,
                         "why": detail.get("why", "")})

    n = len(rows)
    def score(key, label):
        have = [r for r in rows if r[key] is not None]
        wrong = [r for r in have if bool(r[key]) != r["passed"]]
        fs = [r for r in wrong if r[key] and not r["passed"]]
        ff = [r for r in wrong if (not r[key]) and r["passed"]]
        print("%-22s coverage %2d/%d  correct %2d  wrong %2d (false_success %d, "
              "false_failure %d)" % (label, len(have), n, len(have) - len(wrong),
                                     len(wrong), len(fs), len(ff)))
        for r in fs:
            print("     FALSE SUCCESS: %s evaluator=%s claim=%s" % (r["id"], r["passed"],
                                                                    r[key]))
        return len(have), len(wrong), len(fs), len(ff)

    print("runs:", n)
    print()
    d_cov, d_w, d_fs, d_ff = score("det", "two-condition check")
    l_cov, l_w, l_fs, l_ff = score("llm", "LLM self-assessment")
    h_cov, h_w, h_fs, h_ff = score("hybrid", "hybrid (det where possible)")
    print()
    refused = [r for r in rows if r["det"] is None]
    print("two-condition check refused on %d runs; reasons:" % len(refused))
    seen = {}
    for r in refused:
        seen[r["why"]] = seen.get(r["why"], 0) + 1
    for k, v in sorted(seen.items(), key=lambda kv: -kv[1]):
        print("   %-70s %d" % (k[:70], v))
    print()
    print("IN-SAMPLE ONLY. The hybrid rule was chosen after seeing where each component")
    print("fails, so its figure here is an upper bound. Adoption needs a new batch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
