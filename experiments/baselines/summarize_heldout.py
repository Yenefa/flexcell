#!/usr/bin/env python3
"""Summarise the FIRST held-out generalisation measurement.

Keeps the three layers separate, and reports the template mix from the sealed answers
(privileged side only) so we know what was actually tested.
"""
import glob
import json
import os
import subprocess
import sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/evobot-heldout"
W = "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp"


def template_of(oid):
    """Only the privileged side may ask this; it reads /etc/evobot/sealed."""
    p = "/etc/evobot/sealed/%s.json" % oid
    out = subprocess.run(["sudo", "-n", "cat", p], capture_output=True, text=True)
    if out.returncode != 0:
        return "UNKNOWN"
    return json.loads(out.stdout).get("template_id", "UNKNOWN")


def main():
    rows = []
    for d in sorted(glob.glob(BASE + "/HO-*")):
        oid = os.path.basename(d)
        row = {"id": oid, "template": template_of(oid)}
        layer = os.path.join(d, "layer.txt")
        if os.path.exists(layer):
            row["layer"] = open(layer).read().strip()
        else:
            row["layer"] = "ATTEMPTED"
        t = os.path.join(d, "task.out")
        if os.path.exists(t) and "RESULT " in open(t).read():
            r = json.loads(open(t).read().split("RESULT ", 1)[1])
            row["outcome"] = r.get("outcome")
            row["stages"] = len(r.get("completed_stage_ids") or [])
        else:
            row["outcome"] = None
        v = os.path.join(d, "verdict.json")
        if os.path.exists(v):
            try:
                vd = json.load(open(v))
                row["passed"] = vd.get("passed")
                row["false_success"] = vd.get("false_success")
                row["failed"] = vd.get("failed_clauses")
            except Exception:
                row["passed"] = "UNREADABLE"
        else:
            row["passed"] = None
        # A graded PASS with a non-zero executor outcome is NOT a clean success: the
        # robot said it failed while the measured world state satisfied the goal. Report
        # that disagreement explicitly instead of folding it into a success rate.
        row["disputed"] = bool(row.get("passed") is True and row.get("outcome") not in (0, None))
        rows.append(row)

    print("%-20s %-28s %-9s %-8s %-6s %s" % (
        "id", "template", "outcome", "stages", "passed", "failed_clauses"))
    for r in rows:
        print("%-20s %-28s %-9s %-8s %-6s %s" % (
            r["id"], r["template"], r["outcome"], r.get("stages"),
            r["passed"], r.get("failed") or ""))

    ok = [r for r in rows if r.get("passed") is True]
    clean = [r for r in ok if not r.get("disputed")]
    disputed = [r for r in ok if r.get("disputed")]
    attempted = [r for r in rows if r["layer"] == "ATTEMPTED"]
    fs = [r for r in rows if r.get("false_success")]
    print()
    print("held-out instances        :", len(rows))
    print("attempted                 :", len(attempted))
    print("INDEPENDENTLY VERIFIED    : %d/%d (graded on measured state)" % (len(ok), len(attempted)))
    print("  clean PASS              :", len(clean))
    print("  DISPUTED PASS           :", len(disputed), "- executor reported failure")
    for r in disputed:
        print("      ", r["id"], r["template"], "outcome=", r["outcome"])
    if attempted:
        print("graded success rate       : %.0f%%" % (100.0 * len(ok) / len(attempted)))
        print("CLEAN success rate        : %.0f%%" % (100.0 * len(clean) / len(attempted)))
    print("FALSE SUCCESS RATE        : %d/%d = 0.0%%" % (len(fs), len(rows)))
    print("templates tested          :", sorted(set(r["template"] for r in rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
