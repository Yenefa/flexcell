#!/usr/bin/env python3
# Demonstrate the planner order rule ACTUALLY FIRING when an entry authorises it.
# WHY: the rule is gated by order_rule_admitted, which needs an experience item with
# an _entry_id. All 44 archive observations with an experience list carry legacy
# {lesson, failure_class} items whose _entry_id is None. So the rule was measured and
# unit-tested but NEVER observed firing on real data. A rule nobody has seen fire is a
# claim, not a capability. This wires the real chain and keeps the negative control.
import json
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))
sys.path.insert(0, os.path.join(WT, "runtime", "planner"))

import delivery  # noqa: E402
import agent_planner  # noqa: E402

OBS = {"instruction": ("Move the blue block to the left bin, passing "
                      "through the right bin first."),
       "objects": [{"name": "b", "color": "blue"}],
       "zones": [{"name": "zone_1", "position": [0.12, -0.15, 0.0175]},
                 {"name": "zone_2", "position": [0.25, 0.05, 0.0175]}]}
REVERSED = {"moves": [{"object": "b", "zone": "zone_1"},
                      {"object": "b", "zone": "zone_2"}]}


def _order_entry():
    return {"entry_id": "E3-order-pass-through-first",
            "failure_class": "order_clause_violated",
            "suggested_action": ("When the instruction says pass through a bin first, "
                                 "the first move must target that bin."),
            "version": {"status": "ACTIVE"},
            "consumer": "planner"}


def demonstrate():
    entry = _order_entry()
    without = agent_planner.validate_plan(REVERSED, OBS)
    delivered = delivery.deliver_planner(entry, OBS)
    with_entry = agent_planner.validate_plan(REVERSED, delivered)
    problems_without = without[1] if isinstance(without, tuple) else without
    problems_with = with_entry[1] if isinstance(with_entry, tuple) else with_entry
    return {"entry_id": entry["entry_id"],
            "delivered_experience": delivered.get("experience"),
            "reversed_plan_without_entry": without,
            "reversed_plan_with_entry": with_entry,
            "gate_fired": bool(problems_with) and not bool(problems_without),
            "claim": ("the same reversed plan validates cleanly without the delivered "
                      "entry and is refused with it: the rule is authorisable through "
                      "the real delivery channel, not dead code")}


if __name__ == "__main__":
    print(json.dumps(demonstrate(), indent=2, ensure_ascii=False))
