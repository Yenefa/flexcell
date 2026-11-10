#!/usr/bin/env python3
"""EvoBot Baseline A — deterministic composite executor.

This arm does NOT plan. It is handed a stage list derived mechanically from the task
spec by `plan_from_spec`, and it executes it. Its purpose is to measure what the
EXISTING robot stack can already do when someone else does the thinking, so that any
later agent advantage is attributable to the agent and not to the stack.

It is deliberately dumb: no recovery choice, no re-planning, no experience. If
Baseline A already solves a template, that template does not test autonomy and must
not be used to claim it.
"""
import json
import sys
from pathlib import Path


def plan_from_spec(spec):
    """Turn a TaskSpec into an explicit composite stage list (mechanical rules only).

      - explicit expected_goal.order wins;
      - otherwise stage order follows the declared object order;
      - a relay template (T05) inserts an intermediate place at the first zone.
    """
    zones = {z["name"]: z["pose"] for z in spec["zones"]}
    placement = dict(spec["expected_goal"].get("placement") or {})
    order = list(spec["expected_goal"].get("order") or [])
    if not order:
        order = [o["name"] for o in spec["objects"] if o["name"] in placement]

    stages = []
    for i, name in enumerate(order):
        zone = placement[name]
        if spec["template_id"] == "T05_relay" and len(zones) > 1:
            first = sorted(zones)[0]
            if first != zone:
                stages.append({"stage_id": "%s-relay-%d" % (name, i),
                               "object_name": name,
                               "place_pose": list(zones[first])})
        stages.append({"stage_id": "%s-%d" % (name, i),
                       "object_name": name, "place_pose": list(zones[zone])})
    return stages


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print("usage: baseline_a_composite.py <spec.json>", file=sys.stderr)
        return 2
    spec = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    stages = plan_from_spec(spec)
    print(json.dumps({"task_id": spec["task_id"], "stages": stages}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
