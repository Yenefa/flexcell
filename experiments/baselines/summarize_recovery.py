#!/usr/bin/env python3
"""Summarise the Level 3 recovery experiment.

Classifies each instance into one of four outcomes, which is the whole point:
  FIRST_TRY   succeeded without help
  RECOVERED   failed, recovery was attempted, final state passed
  STILL_FAIL  failed and stayed failed
  HARNESS     the run never got a fair attempt

Recovery is only credited when the INDEPENDENT evaluator passes the final state. A
retry that merely looks better is not a recovery.
"""
import glob
import json
import os
import sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/evobot-recover"


def attempt(d, name):
    p = os.path.join(d, name)
    if not os.path.exists(p):
        return None
    txt = open(p, encoding="utf-8", errors="replace").read()
    if "RESULT " not in txt:
        return None
    return json.loads(txt.split("RESULT ", 1)[1])


def decision_action(path):
    if not os.path.exists(path):
        return None
    try:
        doc = json.load(open(path))
    except Exception:
        return None
    if isinstance(doc.get("decision"), dict):
        return doc["decision"].get("action")
    return doc.get("action")


def main():
    rows = []
    for d in sorted(glob.glob(BASE + "/HO-*")):
        oid = os.path.basename(d)
        stage = os.path.join(d, "stage.txt")
        if os.path.exists(stage) and open(stage).read().strip() in ("HARNESS", "PLANNING"):
            rows.append({"id": oid, "kind": "HARNESS",
                         "detail": open(stage).read().strip()})
            continue
        a1 = attempt(d, "task.out")
        a2 = attempt(d, "task_retry.out")
        action = decision_action(os.path.join(d, "recovery_decision.json"))
        v = os.path.join(d, "verdict.json")
        passed, false_success = None, None
        if os.path.exists(v):
            try:
                vd = json.load(open(v))
                passed, false_success = vd.get("passed"), vd.get("false_success")
            except Exception:
                pass
        first_ok = bool(a1) and a1.get("outcome") == 0
        retried = os.path.exists(os.path.join(d, "plan_retry.json"))
        if first_ok and passed:
            kind = "FIRST_TRY"
        elif retried and passed:
            kind = "RECOVERED"
        elif passed is False:
            kind = "STILL_FAIL"
        else:
            kind = "UNKNOWN"
        rows.append({"id": oid, "kind": kind, "action": action,
                     "a1_err": None if not a1 else a1.get("error_code"),
                     "a2_err": None if not a2 else a2.get("error_code"),
                     "passed": passed, "false_success": false_success})

    print("%-20s %-11s %-11s %-6s %-6s %s" % (
        "task", "outcome", "action", "a1err", "a2err", "graded"))
    for r in rows:
        print("%-20s %-11s %-11s %-6s %-6s %s" % (
            r["id"], r["kind"], r.get("action"), r.get("a1_err"), r.get("a2_err"),
            r.get("passed")))

    counts = {}
    for r in rows:
        counts[r["kind"]] = counts.get(r["kind"], 0) + 1
    failed_first = [r for r in rows if r["kind"] in ("RECOVERED", "STILL_FAIL")]
    recovered = [r for r in rows if r["kind"] == "RECOVERED"]
    fs = [r for r in rows if r.get("false_success")]
    graded = [r for r in rows if r.get("passed") is not None]
    print()
    print("instances              :", len(rows))
    print("outcome counts         :", counts)
    print("first-attempt failures :", len(failed_first))
    if failed_first:
        print("RECOVERY RATE          : %d/%d = %.0f%%" % (
            len(recovered), len(failed_first),
            100.0 * len(recovered) / len(failed_first)))
    if graded:
        ok = sum(1 for r in graded if r["passed"])
        print("FINAL PASS RATE        : %d/%d = %.0f%%" % (
            ok, len(graded), 100.0 * ok / len(graded)))
    print("FALSE SUCCESS RATE     : %d/%d" % (len(fs), max(1, len(graded))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
