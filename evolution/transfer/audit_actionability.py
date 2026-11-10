#!/usr/bin/env python3
"""Audit whether each stored lesson can possibly change an agent plan.

WHY: two independent B/C experiments measured byte-identical plans. "Experience had no
effect" is a null result, not an explanation. This audit finds the MECHANISM.

The agent plan schema is {moves:[{object, zone, why}], unmoved, confidence, uncertainty}.
It contains NO landing coordinates: those are computed afterwards by spread_destinations.
So a lesson about landing spots cannot change a plan no matter how true it is - the
planner never produces that field. A lesson is ACTIONABLE only if it maps onto a field
the planner actually controls.
"""
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))
import store

DOWNSTREAM = ("landing", "spot", "coordinate", "pose", "spread", "centre", "center")
HARNESS = ("domain", "participant", "admission", "launch", "stack")


def classify_actionability(lesson):
    text = lesson.lower()
    if any(w in text for w in DOWNSTREAM):
        return ("DOWNSTREAM_CODE",
                "describes a landing/spread detail computed AFTER planning; the "
                "planner emits zone names only, so this cannot change a plan")
    if any(w in text for w in HARNESS):
        return ("HARNESS",
                "describes a runtime/harness concern outside the planner entirely")
    if any(w in text for w in ("object", "unmoved", "zone", "order")):
        return "PLANNER_ACTIONABLE", "maps onto a field the planner controls"
    return "UNCLEAR", "cannot be mapped to any plan field"


def main():
    path = os.path.join(WT, "evolution", "experience", "records.jsonl")
    rows = [r for r in store.read(path) if r.get("validated")]
    counts = {}
    for r in rows:
        label, why = classify_actionability(r["lesson"])
        counts[label] = counts.get(label, 0) + 1
        print("%-18s %s" % (label, r["lesson"][:92]))
        print("%-18s -> %s" % ("", why))
    print()
    print("validated lessons:", len(rows))
    for k, v in sorted(counts.items()):
        print("  %-22s %d" % (k, v))
    actionable = counts.get("PLANNER_ACTIONABLE", 0)
    print()
    print("ACTIONABLE FRACTION: %d/%d" % (actionable, len(rows)))
    print("At most %d of %d lessons could ever move a plan." % (actionable, len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
