#!/usr/bin/env python3
"""Tabulate what the goal check actually concluded on each run.

WHY THIS IS WRITTEN OUT AS CODE: my first archival table labelled a run "SATISFIED" merely
because goal_check.json contained a "stages" list. That run's decision was action=resume,
i.e. the check had compared the stages and found the goal NOT satisfied - the exact opposite
of the label. The label must come from the DECISION, not from the presence of a file.
"""
import glob
import json
import os
import sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/evobot-batch3"


def read(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return {}


def classify(d):
    dec_file = read(os.path.join(d, "recovery_decision.json"))
    dec = dec_file.get("decision") or dec_file
    reason = str(dec.get("reason") or dec.get("why") or "")
    action = dec.get("action")
    gc = read(os.path.join(d, "goal_check.json"))

    if "goal already satisfied" in reason:
        # every stage measured inside the plan's own tolerance -> retry skipped
        detail = ", ".join("%s %.1fmm" % (s.get("object"), 1000 * s["distance_m"])
                           for s in gc.get("stages", []) if "distance_m" in s)
        return "SKIPPED (goal met)", detail
    if "REFUSED" in str(gc.get("decision", "")):
        return "REFUSED (ordering)", ",".join(gc.get("repeated_objects", []))
    if gc.get("stages"):
        far = [s for s in gc["stages"] if s.get("status") != "AT_TARGET"]
        detail = ", ".join("%s %s" % (s.get("object"), s.get("status"))
                           for s in far) or "all at target"
        return "checked, NOT met", detail
    return "not consulted", task_outcome(d)


def task_outcome(d):
    out = os.path.join(d, "task.out")
    if not os.path.exists(out):
        return "?"
    txt = open(out, encoding="utf-8", errors="replace").read()
    i = txt.rfind("RESULT ")
    if i < 0:
        return "?"
    try:
        return "task_outcome=%s" % json.loads(txt[i + 7:]).get("outcome")
    except Exception:
        return "?"


def main():
    print("%-20s %-8s %-8s %-18s %-10s %s" % ("run", "B", "R", "goal_check",
                                              "action", "detail"))
    tally = {}
    for d in sorted(glob.glob(os.path.join(BASE, "HO-*"))):
        oid = os.path.basename(d)
        b = read(os.path.join(d, "verdict_after1.json")).get("passed")
        r = read(os.path.join(d, "verdict.json")).get("passed")
        dec_file = read(os.path.join(d, "recovery_decision.json"))
        dec = dec_file.get("decision") or dec_file
        label, detail = classify(d)
        tally[label] = tally.get(label, 0) + 1
        print("%-20s %-8s %-8s %-18s %-10s %s" % (oid, b, r, label,
                                                  dec.get("action"), detail))
    print()
    for k in sorted(tally):
        print("%-22s %d" % (k, tally[k]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
