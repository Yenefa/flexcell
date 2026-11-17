#!/usr/bin/env python3
"""Which of the routings the objective NAMES are actually carrying an entry.

THE GAP THIS EXISTS FOR
    The objective names four routings:

        操作顺序经验交给规划器        order    -> planner
        落点间距经验交给落点分配策略  spacing  -> spread_policy
        抓放恢复经验交给执行器        recovery -> executor_recovery
        ROS 启动经验归入开发经验      ROS launch -> development

    Three of them carry a live entry. The fourth is DECLARED in consumers.py, is counted as
    "implemented" because its entrypoint file exists, and has never carried anything - and
    nothing anywhere said so. A registry that lists a destination is not evidence that
    anything was ever sent there.

    Worse, when a ROS-launch lesson IS offered to it, delivery returns UNSUPPORTED: the
    routing exists and nothing can arrive. That is the same "routed but undeliverable"
    defect this package has fixed twice for other consumers, and it had never been checked
    for this one.

WHAT THIS DOES NOT DO
    It does not invent a delivery path to make the number look better. A development
    experience lands in development_skills/registry.json, which is prose for a coding agent
    - there is no deterministic way to check that a lesson changed an agent's behaviour, and
    claiming otherwise would be the exact overstatement that registry's own README warns
    about. So the consumer's coverage is reported as NAMED BUT EMPTY, and that is the honest
    state until somebody builds a checkable delivery for it.
"""
import json
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import consumers  # noqa: E402
import store  # noqa: E402

# The four routings the objective states, and the consumer each one maps to. This table is
# the objective's text, not something derived from the code: deriving it would only say what
# the code already believes.
OBJECTIVE_ROUTINGS = (
    ("order (操作顺序)", "planner"),
    ("spread (落点间距)", "spread_policy"),
    ("recovery (抓放恢复)", "executor_recovery"),
    ("ROS launch (ROS 启动)", "development"),
)

CARRIED = "CARRIED"
NAMED_BUT_EMPTY = "NAMED_BUT_EMPTY"
UNDECLARED = "UNDECLARED"


def coverage(store_path, delivery=None):
    """For each named routing: does any ACTIVE entry actually arrive at its consumer?

    'Arrives' means an ACTIVE entry names that consumer AND delivery can render the entry
    for it. An entry that routes but cannot be delivered is reported as NAMED_BUT_EMPTY with
    a distinct reason, because the two failures need different fixes: one needs an entry,
    the other needs a delivery path.
    """
    import delivery as delivery_mod
    rows = [r for r in store.read(store_path)
            if (r.get("version") or {}).get("status") == "ACTIVE"]
    out = []
    for label, consumer in OBJECTIVE_ROUTINGS:
        declared = consumer in consumers.CONSUMERS
        mine = [r for r in rows if r.get("consumer") == consumer]
        deliverable = []
        for row in mine:
            try:
                verdict = delivery_mod.deliver(row, None).get("verdict")
            except Exception:  # noqa: BLE001 - a crashed renderer is a non-delivery
                verdict = "ERROR"
            if verdict == delivery_mod.DELIVERED:
                deliverable.append(row.get("version", {}).get("label"))
        if not declared:
            state, why = UNDECLARED, "no consumer in this stack declares it"
        elif deliverable:
            state, why = CARRIED, "delivered by %s" % (deliverable,)
        elif mine:
            state = NAMED_BUT_EMPTY
            why = ("%d ACTIVE entr(ies) name it but delivery refuses: %s"
                   % (len(mine), delivery_mod.deliver(mine[0], None).get("why")))
        else:
            state, why = NAMED_BUT_EMPTY, "no ACTIVE entry names this consumer"
        out.append({"routing": label, "consumer": consumer, "state": state, "why": why,
                    "active_entries": [r.get("version", {}).get("label") for r in mine]})
    # A NAMED ROUTING CAN BE SERVED FROM A DIFFERENT ADDRESS. The objective says a ROS
    # launch lesson belongs in development experience; in this stack it is executable as a
    # config change and therefore lives under "harness". Reporting only "named but empty"
    # would say the lesson is missing when it exists and acts - the address differs, and
    # that difference is a fact worth stating rather than a number worth hiding.
    served_elsewhere = {}
    for row in [r for r in rows if r.get("consumer") not in
                {c for _l, c in OBJECTIVE_ROUTINGS}]:
        consumer = row.get("consumer")
        try:
            verdict = delivery_mod.deliver(row, None).get("verdict")
        except Exception:  # noqa: BLE001
            verdict = "ERROR"
        if verdict == delivery_mod.DELIVERED:
            served_elsewhere.setdefault(consumer, []).append(
                row.get("version", {}).get("label"))
    return {"routings": out,
            "carried": sum(1 for r in out if r["state"] == CARRIED),
            "named": len(out),
            # consumers the objective did NOT name but that do carry a delivered entry
            "carried_by_an_unnamed_consumer": served_elsewhere,
            "claim": ("a routing is CARRIED only when an ACTIVE entry reaches its consumer; "
                      "a declared consumer with no arriving entry is NAMED_BUT_EMPTY. A "
                      "lesson can also act from a consumer the objective did not name, and "
                      "that is reported separately rather than counted as coverage")}


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        WT, "setup", "acceptance", "evobot_continual_chain_20261118", "records_v2.jsonl")
    print(json.dumps(coverage(path), indent=2, ensure_ascii=False))
