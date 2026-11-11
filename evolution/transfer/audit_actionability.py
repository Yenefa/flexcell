#!/usr/bin/env python3
"""Audit whether each stored lesson can possibly change an agent plan.

WHY: two independent B/C experiments measured byte-identical plans. "Experience had no
effect" is a null result, not an explanation. This audit finds the MECHANISM.

The agent plan schema is {moves:[{object, zone, why}], unmoved, confidence, uncertainty}.
It contains NO landing coordinates: those are computed afterwards by spread_destinations.
So a lesson about landing spots cannot change a plan no matter how true it is - the
planner never produces that field. A lesson is ACTIONABLE only if it maps onto a field
the planner actually controls.

CORRECTION (round 14): this audit used to filter on `validated`. After the provenance fix that
field means "the OLD seeder ran" and no longer means trustworthy, so the filter silently
reported on the least trustworthy records and ignored the verified ones. It now partitions by
provenance_verified and reports BOTH cohorts, because a single blended number hid which half
of the store the conclusion applied to.
"""
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))
import store

DOWNSTREAM = ("landing", "spot", "coordinate", "pose", "spread", "centre", "center")
HARNESS = ("domain", "participant", "admission", "launch", "stack")


def classify_actionability(lesson):
    text = (lesson or '').lower()
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


def cohort(rows, label):
    counts = {}
    for r in rows:
        tag, why = classify_actionability(r.get("lesson"))
        counts[tag] = counts.get(tag, 0) + 1
        print("  %-18s %s" % (tag, (r.get("lesson") or "")[:86]))
    print()
    print("  %s: %d record(s)" % (label, len(rows)))
    for k, v in sorted(counts.items()):
        print("    %-22s %d" % (k, v))
    actionable = counts.get("PLANNER_ACTIONABLE", 0)
    print("  ACTIONABLE FRACTION (%s): %d/%d" % (label, actionable, len(rows)))
    return actionable, len(rows)


def main():
    path = os.path.join(WT, "evolution", "experience", "records.jsonl")
    rows = store.read(path)
    verified = [r for r in rows if r.get("provenance_verified") is True]
    unverified = [r for r in rows if r.get("provenance_verified") is not True]
    print("=== VERIFIED cohort (provenance checked mechanically) ===")
    av, nv = cohort(verified, "verified")
    print()
    print("=== UNVERIFIED cohort (legacy: no provenance check existed when written) ===")
    au, nu = cohort(unverified, "unverified")
    print()
    print("=== combined ===")
    print("  total records: %d" % len(rows))
    print("  ACTIONABLE FRACTION (all): %d/%d" % (av + au, nv + nu))
    if nu and not nv:
        print()
        print("  NOTE: every record in the store is unverified, so this audit describes records")
        print("        whose evidence an independent review found 3 of 4 cannot reproduce.")


if __name__ == "__main__":
    main()
