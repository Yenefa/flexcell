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
# TWO DIFFERENT GAPS that used to report as one:
#   NO_ENTRY     the delivery path works; nothing has been routed here yet
#   NO_DELIVERY  an entry exists for this consumer but cannot reach it
# They need different work, so blending them lets one hide behind the other.
NO_ENTRY = "NO_ENTRY"
NO_DELIVERY = "NO_DELIVERY"


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
            verdict = delivery_mod.deliver(mine[0], None)
            # a consumer with no renderer at all is a CODE gap; one whose renderer works but
            # produced nothing is a DIFFERENT gap
            state = NO_DELIVERY if verdict.get("verdict") == delivery_mod.UNSUPPORTED \
                else NAMED_BUT_EMPTY
            why = ("%d ACTIVE entr(ies) name it but delivery refuses: %s"
                   % (len(mine), verdict.get("why")))
        else:
            # Does a path exist at all? Asking delivery with a probe would be wrong for the
            # planner: it needs an observation, so a bare probe returns UNSUPPORTED and the
            # consumer would be reported as having no delivery path when it has one. The
            # registered renderer is the direct evidence, and the non-text consumers are
            # declared in deliver_non_text.
            reachable = (consumer in getattr(delivery_mod, "RENDERERS", {})
                         or consumer in ("spread_policy", "executor_recovery", "harness",
                                         "development"))
            state = NO_ENTRY if reachable else NO_DELIVERY
            why = ("no ACTIVE entry names this consumer (a delivery path %s)"
                   % ("exists" if reachable else "does NOT exist"))
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
    # A CONSUMER CAN ALSO ACT WITHOUT AN ENTRY - a rule wired straight into the code path.
    # That is NOT coverage and it is worse than an empty routing: an empty routing does
    # nothing, while an unbacked live rule changes behaviour and cannot be reviewed, probed
    # for misuse, recorded, revised or retired, because there is no entry to hang any of
    # that on. Detected for the planner specifically, because that is where it happened.
    unbacked = []
    try:
        sys.path.insert(0, os.path.join(WT, "runtime", "planner"))
        import agent_planner
        # A reversed plan and an observation with no delivered entry: if the planner refuses
        # it anyway, a rule is live that nothing backs.
        probe_obs = {"instruction": ("the blue block must be put there FIRST"),
                     "objects": [{"name": "a", "color": "red"},
                                 {"name": "b", "color": "blue"}],
                     "zones": [{"name": "z", "position": [0.0, 0.0, 0.0]}]}
        _p, problems = agent_planner.validate_plan(
            {"moves": [{"object": "a", "zone": "z"},
                       {"object": "b", "zone": "z"}]}, probe_obs)
        if any("FIRST" in str(x) for x in problems):
            unbacked.append("planner:order_rule")
    except Exception:  # noqa: BLE001 - a missing planner is not an unbacked rule
        pass
    return {"routings": out,
            "carried": sum(1 for r in out if r["state"] == CARRIED),
            "named": len(out),
            "live_rules_with_no_entry": unbacked,
            # consumers the objective did NOT name but that do carry a delivered entry
            "carried_by_an_unnamed_consumer": served_elsewhere,
            "claim": ("a routing is CARRIED only when an ACTIVE entry reaches its consumer. "
                      "NO_ENTRY (path works, nothing routed) and NO_DELIVERY (entry exists, "
                      "cannot arrive) are reported apart because they need different work. A "
                      "lesson can also act from a consumer the objective did not name, and "
                      "that is reported separately rather than counted as coverage. A rule "
                      "live in the code path with no entry behind it is reported as "
                      "live_rules_with_no_entry - it is worse than an empty routing, not "
                      "better, because it cannot be reviewed or retired")}


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        WT, "setup", "acceptance", "evobot_continual_chain_20261118", "records_v2.jsonl")
    print(json.dumps(coverage(path), indent=2, ensure_ascii=False))
