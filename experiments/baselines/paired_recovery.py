#!/usr/bin/env python3
"""Paired Baseline-B vs Recovery analysis.

ONE run yields both arms, which is what makes this an exact pair:
  B (no recovery) = the first attempt, graded on the state it left behind
  R (recovery)    = the final state after a bounded retry
Same plan, same world, same evaluator, same seed. So any difference is attributable to
the retry alone, and no between-run variance can explain it.

Reports the paired transition table rather than two independent rates, because with n=16
the transition counts are the honest evidence.
"""
import glob
import json
import os
import sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/evobot-pair16"


def load(p):
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def result_of(path):
    if not os.path.exists(path):
        return None
    txt = open(path, encoding="utf-8", errors="replace").read()
    if "RESULT " not in txt:
        return None
    return json.loads(txt.split("RESULT ", 1)[1])


def main():
    rows = []
    for d in sorted(glob.glob(BASE + "/HO-*")):
        stage = os.path.join(d, "stage.txt")
        if os.path.exists(stage) and open(stage).read().strip() in ("HARNESS", "PLANNING"):
            rows.append({"id": os.path.basename(d), "kind": "HARNESS"})
            continue
        b1 = load(os.path.join(d, "verdict_after1.json"))
        bR = load(os.path.join(d, "verdict.json"))
        a1 = result_of(os.path.join(d, "task.out"))
        a2 = result_of(os.path.join(d, "task_retry.out"))
        dec = load(os.path.join(d, "recovery_decision.json")) or {}
        action = (dec.get("decision") or {}).get("action") if dec.get("decision") else dec.get("action")
        rows.append({"id": os.path.basename(d), "kind": "RUN",
                     "b_pass": None if b1 is None else b1.get("passed"),
                     "r_pass": None if bR is None else bR.get("passed"),
                     "a1_err": None if not a1 else a1.get("error_code"),
                     "a2_err": None if not a2 else a2.get("error_code"),
                     "action": action,
                     "false_success": (b1 or {}).get("false_success") or (bR or {}).get("false_success")})

    runs = [r for r in rows if r["kind"] == "RUN"]
    print("%-20s %-8s %-8s %-8s %-8s %s" % (
        "task", "B", "R", "a1err", "a2err", "action"))
    for r in runs:
        print("%-20s %-8s %-8s %-8s %-8s %s" % (
            r["id"], r["b_pass"], r["r_pass"], r["a1_err"], r["a2_err"], r["action"]))

    both = sum(1 for r in runs if r["b_pass"] and r["r_pass"])
    gained = sum(1 for r in runs if not r["b_pass"] and r["r_pass"])
    lost = sum(1 for r in runs if r["b_pass"] and not r["r_pass"])
    neither = sum(1 for r in runs if not r["b_pass"] and not r["r_pass"])
    harness = len(rows) - len(runs)
    b_total = sum(1 for r in runs if r["b_pass"])
    r_total = sum(1 for r in runs if r["r_pass"])
    fs = sum(1 for r in runs if r["false_success"])
    retried = sum(1 for r in runs if r["action"] in ("resume", "respread", "redispatch", "reobserve"))

    print()
    print("instances            :", len(rows))
    print("usable runs          :", len(runs))
    print("harness failures     :", harness)
    print("B pass (first try)   : %d/%d" % (b_total, len(runs)))
    print("R pass (after retry) : %d/%d" % (r_total, len(runs)))
    print("paired transitions   : both=%d gained=%d lost=%d neither=%d" % (
        both, gained, lost, neither))
    print("retries attempted    :", retried)
    if retried:
        print("RECOVERY RATE        : %d/%d = %.0f%%" % (
            gained, retried, 100.0 * gained / retried))
    print("FALSE SUCCESS RATE   : %d/%d" % (fs, max(1, len(runs))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
