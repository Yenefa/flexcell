#!/usr/bin/env python3
"""Score the ORDER-constraint batch and separate planning from execution.

WHY THE SEPARATION MATTERS: a pass rate cannot say whether the agent understood the sequence.
The plan could list the right order while execution stops early, or the plan could be reversed
and still end with both boxes in the right bin.

WHY THERE ARE THREE EXECUTION STATES, NOT TWO: the first version of this script returned a
single boolean and I read False as "executed out of order". The evidence said otherwise -
observed was ["target_box_a"] with matched=1 and out_of_order=[], meaning the second move was
NEVER RECORDED because the run stopped on that object. Calling that "out of order" invents a
failure mode that did not happen. So:
    in-order     the required sequence was fully observed, in the required sequence
    INCOMPLETE   observed is a correct strict prefix - the run stopped before the later move
    WRONG-ORDER  moves were observed but not in the required sequence

Runs as root: the ordered answer lives in the sealed directory. This is analysis, not
something the agent sees.
"""
import glob
import json
import math
import os
import subprocess
import sys

WT = "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp"
BASE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/evobot-batch4"
SEALED = "/etc/evobot/sealed"


def read(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def classify(seq, required):
    seq = list(seq)
    if not required:
        return "no-requirement"
    if seq[:len(required)] == required:
        return "in-order"
    if len(seq) < len(required) and seq == required[:len(seq)]:
        return "INCOMPLETE"
    return "WRONG-ORDER"


def main():
    v = os.path.join(WT, "experiments", "baselines", "validate_batch.py")
    rc = subprocess.run([sys.executable, v, BASE], capture_output=True, text=True)
    print(rc.stdout.strip()[:600])
    if rc.returncode != 0:
        print("REFUSING to report: the batch failed structural validation.")
        return 1

    rows = []
    for d in sorted(glob.glob(os.path.join(BASE, "HO-*"))):
        oid = os.path.basename(d)
        ans = read(os.path.join(SEALED, oid + ".json")) or {}
        req = (ans.get("expected_goal") or {}).get("order") or []
        plan = read(os.path.join(d, "plan.json")) or {}
        planned = [s.get("object_name") for s in plan.get("stages", [])]
        obs = read(os.path.join(d, "observation_after1.json")) or {}
        seq = obs.get("move_sequence") or []
        v1 = read(os.path.join(d, "verdict_after1.json")) or {}
        vv = read(os.path.join(d, "verdict.json")) or {}
        clauses = {c.get("clause"): c.get("ok") for c in (v1.get("clauses") or [])}
        rows.append({
            "id": oid, "required": req,
            "plan_state": classify(planned, req),
            "exec_state": classify(seq, req),
            "observed": seq,
            "order_clause": clauses.get("order"),
            "b": bool(v1.get("passed")), "r": bool(vv.get("passed")),
        })

    print()
    print("%-20s %-8s %-14s %-14s %-7s %-6s %s" % (
        "run", "required", "plan", "exec", "ordercl", "B", "R"))
    for x in rows:
        print("%-20s %-8s %-14s %-14s %-7s %-6s %s" % (
            x["id"], ",".join(n.replace("target_box_", "") for n in x["required"]),
            x["plan_state"], x["exec_state"], x["order_clause"], x["b"], x["r"]))

    n = len(rows)
    print()
    for label, k in (
            ("planning in-order", sum(1 for x in rows if x["plan_state"] == "in-order")),
            ("execution in-order", sum(1 for x in rows if x["exec_state"] == "in-order")),
            ("arm B pass", sum(1 for x in rows if x["b"])),
            ("arm R pass", sum(1 for x in rows if x["r"]))):
        p, lo, hi = wilson(k, n)
        print("%-22s %2d/%-2d = %5.1f%% (%.1f-%.1f%%)" % (label, k, n,
                                                          100 * p, 100 * lo, 100 * hi))

    incomplete = [x["id"] for x in rows if x["exec_state"] == "INCOMPLETE"]
    wrong = [x["id"] for x in rows if x["exec_state"] == "WRONG-ORDER"]
    print()
    print("execution INCOMPLETE (a move was never recorded):", len(incomplete),
          incomplete or "-")
    print("execution WRONG-ORDER (moves happened out of sequence):", len(wrong),
          wrong or "-")
    if incomplete:
        print("  -> these did not reorder the work; the run stopped before the later move")
    if wrong:
        print("  -> these genuinely reordered the work")
    print()
    print("READING: T14 constrains WHEN, not just where. Every earlier held-out set varied")
    print("only the world, so a planner could pass them without reasoning about sequence.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
