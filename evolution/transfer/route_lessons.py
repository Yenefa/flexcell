#!/usr/bin/env python3
"""Route each stored lesson to the component that can actually act on it.

THE MECHANISM THIS FIXES: two B/C experiments measured byte-identical plans. The audit
found why - the agent plan is {moves:[{object, zone}], unmoved}, so it has no landing
coordinates at all. Three of four validated lessons describe landing spots or harness
concerns, which the planner cannot express. Injecting them into the planner prompt was
therefore guaranteed to change nothing, while still costing more tokens.

A lesson about landing spots is not useless - it is already implemented, in
experiments/baselines/spread_destinations.py. The mistake was the DELIVERY ADDRESS.
This module routes by consumer and checks whether that consumer already implements it.
"""
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))
import store

# ORDER MATTERS: the harness rule is the most specific, so it is checked first. The
# domain-id lesson also contains "distinct", and putting spread_policy first mis-routed it
# to the spacing code - a real bug the tests caught.
RULES = [
    ("harness", ("domain", "participant", "admission", "launch", "stalled"),
     "config/cyclonedds.xml"),
    ("spread_policy", ("landing", "spot", "centre", "center", "same bin"),
     "experiments/baselines/spread_destinations.py"),
    ("planner", ("object", "unmoved", "zone", "order", "further", "except"),
     "runtime/planner/agent_planner.py"),
]

SIGNATURES = {
    "spread_policy": "def spread(",
    "harness": "MaxAutoParticipantIndex",
    "planner": "def describe(",
}


def route(lesson):
    text = lesson.lower()
    for consumer, words, path in RULES:
        if any(w in text for w in words):
            return consumer, path
    return "unrouted", None


def implemented_in(path, signature):
    full = os.path.join(WT, path)
    if not os.path.exists(full):
        return False
    src = open(full, encoding="utf-8", errors="replace").read()
    return signature in src


def main():
    path = os.path.join(WT, "evolution", "experience", "records.jsonl")
    rows = [r for r in store.read(path) if r.get("validated")]
    print("%-14s %-5s %s" % ("CONSUMER", "DONE", "LESSON"))
    tally = {}
    for r in rows:
        consumer, target = route(r["lesson"])
        done = bool(target) and implemented_in(target, SIGNATURES.get(consumer, ""))
        tally[consumer] = tally.get(consumer, 0) + 1
        print("%-14s %-5s %s" % (consumer, "yes" if done else "NO", r["lesson"][:78]))
    print()
    for k, v in sorted(tally.items()):
        print("  %-14s %d" % (k, v))
    planner = tally.get("planner", 0)
    print()
    print("lessons that belong in the PLANNER PROMPT: %d/%d" % (planner, len(rows)))
    print("The rest are already implemented in code, where they can actually act.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
