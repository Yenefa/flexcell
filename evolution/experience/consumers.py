#!/usr/bin/env python3
"""Which module can actually ACT on an experience entry, and where its entrypoint is.

THE DEFECT THIS REPLACES
    evolution/transfer/route_lessons.py routes a lesson by looking for words in the lesson
    text ("landing", "spot", "domain", ...). It found the right addresses most of the time
    and it also produced the bug its own docstring records: a domain-id lesson contains
    "distinct", so it was routed to the spacing code. Keyword routing is a guess about a
    consumer's capability.

    Here a consumer DECLARES the action kinds it can execute, and the route is the set
    intersection between that declaration and the entry's action_kind. An entry whose
    kind no consumer declares is UNROUTED - and an UNROUTED entry is a fact about the
    stack, not a failure of the entry: it means this robot has nowhere to put that
    knowledge yet, which is exactly what happened to the landing-spot lessons before
    spread_destinations.py existed.

WHY THE ENTRYPOINT IS A PATH + SYMBOL, NOT AN IMPORT
    A consumer is only real if the symbol is present in the tree. implemented() checks
    that mechanically, so "routed" cannot be satisfied by a registry that lies about a
    module that was never written.
"""
import os

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# consumer id -> declaration. action_kinds is the capability claim; entrypoint is where
# the change would land; signature proves the entrypoint exists in this checkout.
CONSUMERS = {
    "planner": {
        "action_kinds": ("move_order", "object_set"),
        "entrypoint": "runtime/planner/agent_planner.py",
        "symbol": "def describe(",
        "delivery": "prompt",
        # A prompt-level delivery cannot be measured without a model call, so the effect
        # prober reports UNMEASURED rather than inventing a difference. Recorded here so
        # the limitation travels with the registry instead of living in someone's memory.
        "measurable_offline": False,
    },
    "spread_policy": {
        "action_kinds": ("landing_spacing",),
        "entrypoint": "runtime/planner/spread_destinations.py",
        "symbol": "def spread(",
        "delivery": "parameter",
        "measurable_offline": True,
    },
    "executor_recovery": {
        "action_kinds": ("recovery_action",),
        "entrypoint": "runtime/recovery/recover.py",
        "symbol": "ACTION_TABLE",
        "delivery": "parameter",
        "measurable_offline": True,
    },
    "harness": {
        "action_kinds": ("harness_config",),
        "entrypoint": "config/cyclonedds.xml",
        "symbol": "MaxAutoParticipantIndex",
        "delivery": "config",
        "measurable_offline": False,
    },
    "development": {
        "action_kinds": ("development",),
        "entrypoint": "development_skills/registry.json",
        "symbol": "evobot-development-skills",
        "delivery": "document",
        # Development skills are for the coding agent. They are deliberately NOT
        # measurable by a robot run, and the master goal keeps them a separate type.
        "measurable_offline": False,
    },
}


class RoutingError(ValueError):
    """The entry names a consumer that cannot act on its action_kind."""


def consumers_for(action_kind):
    """Every consumer that DECLARES it can execute this kind, in a stable order."""
    return sorted(cid for cid, spec in CONSUMERS.items()
                  if action_kind in spec["action_kinds"])


def implemented(consumer):
    """Is the declared entrypoint present, with its symbol, in this checkout?"""
    spec = CONSUMERS.get(consumer)
    if spec is None:
        return False
    full = os.path.join(WT, spec["entrypoint"])
    if not os.path.exists(full):
        return False
    with open(full, encoding="utf-8", errors="replace") as fh:
        return spec["symbol"] in fh.read()


def route(entry):
    """Return (consumer, why). Raises RoutingError when the claim is impossible.

    A declared consumer that cannot act on the kind is REFUSED, not silently rerouted:
    silently rerouting is how a landing-spot lesson ended up in a planner prompt where
    it could not possibly change anything.
    """
    kind = entry.get("action_kind")
    declared = entry.get("consumer")
    capable = consumers_for(kind)
    if not capable:
        return None, ("UNROUTED: no module in this stack declares it can execute %r; "
                      "the entry is stored but cannot act until such a module exists"
                      % (kind,))
    if declared and declared not in capable:
        raise RoutingError(
            "entry names consumer %r but that consumer does not declare %r; "
            "capable consumers are %s" % (declared, kind, capable))
    chosen = declared or capable[0]
    if not implemented(chosen):
        return None, ("UNROUTED: %r declares %r but its entrypoint %s is missing from "
                      "this checkout" % (chosen, kind,
                                         CONSUMERS[chosen]["entrypoint"]))
    return chosen, "routed by declared capability (%s -> %s)" % (kind, chosen)


def table():
    """Human-readable capability table, used by the CLI and by the acceptance verifier."""
    rows = []
    for cid in sorted(CONSUMERS):
        spec = CONSUMERS[cid]
        rows.append({"consumer": cid, "action_kinds": list(spec["action_kinds"]),
                     "entrypoint": spec["entrypoint"], "delivery": spec["delivery"],
                     "implemented": implemented(cid),
                     "measurable_offline": spec["measurable_offline"]})
    return rows


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(table(), indent=2))
    if len(sys.argv) > 1:
        doc = json.loads(open(sys.argv[1], encoding="utf-8").read())
        try:
            print(route(doc))
        except RoutingError as exc:
            print("REFUSED:", exc)
            raise SystemExit(1)
