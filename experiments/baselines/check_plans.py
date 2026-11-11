#!/usr/bin/env python3
"""POST-HOC analysis of Baseline B plans against the sealed answer.

THIS IS NOT THE INDEPENDENT EVALUATOR, AND ITS RESULT IS NOT A SUCCESS CLAIM.

Two things it is NOT:
  - It is not the evaluator. benchmark/evaluators/evaluate.py grades the FINAL
    WORLD STATE after the robot moves. This script grades the PLAN, against
    expected_goal, before anything has moved. A plan can be perfect and the run
    still fail (execution is where this project's remaining failures live), and
    that distinction must never be blurred.
  - It is not a generalisation measurement. It runs on TRAIN instances, whose
    answers are legitimately on disk. Nothing here may be reported as held-out.

It exists to answer one narrow question honestly: did the agent infer the right
object->bin mapping, the right order, and the right route from the instruction?
That is the PLANNING question, and it is separable from execution.

The agent never sees expected_goal. This script runs after the fact, as the
researcher, and it says so in its output.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRAIN = ROOT / "benchmark" / "tasks" / "train"


def final_placement(agent_plan):
    """The bin each object ENDS in, ignoring intermediate hops.

    An object moved twice (relay / revisit) has one final destination: the last
    move that names it. Reading the FIRST move would score a correct relay as
    wrong, which is the same mistake the evaluator avoids by grading the final
    state only.
    """
    final = {}
    for move in agent_plan["moves"]:
        final[move["object"]] = move["zone"]
    return final


def route(agent_plan):
    """Every bin each object is placed into, in order."""
    hops = {}
    for move in agent_plan["moves"]:
        hops.setdefault(move["object"], []).extend(move.get("via") or [])
        hops[move["object"]].append(move["zone"])
    return hops


def move_order(agent_plan):
    """Order of FIRST appearance of each object in the plan."""
    order, seen = [], set()
    for move in agent_plan["moves"]:
        if move["object"] not in seen:
            order.append(move["object"])
            seen.add(move["object"])
    return order


def check_one(plan_dir, task_id):
    task_dir = Path(plan_dir)
    spec = json.loads((TRAIN / (task_id + ".json")).read_text(encoding="utf-8"))
    reply = json.loads((task_dir / "agent_reply.json").read_text(encoding="utf-8"))
    agent_plan = reply.get("agent_plan")
    if not agent_plan:
        # Carry the template even on failure. The first version omitted it, and the
        # batch verifier crashed with KeyError('template') while summarising -- a
        # crash that exits non-zero, so it could not be mistaken for a pass, but it
        # hid the real report behind a traceback. A failure record must be as
        # structurally complete as a success record, or analysing failures is the
        # hard case and analysing successes is the only easy one.
        return {"task_id": task_id,
                "template": spec["template_id"],
                "instruction": spec["instruction"],
                "planned": False,
                "plan_level_correct": False,
                "problems": reply.get("problems"),
                "tokens": (reply.get("usage") or {}).get("tokens")}

    goal = spec["expected_goal"]
    want_placement = dict(goal.get("placement") or {})
    got_placement = final_placement(agent_plan)

    checks = {}
    checks["placement_matches"] = got_placement == want_placement

    # An object the task protects must not be planned to move.
    protected = set(goal.get("unmoved") or [])
    moved = {m["object"] for m in agent_plan["moves"]}
    checks["protected_objects_left_alone"] = not (protected & moved)

    # Order, when the task fixes one.
    want_order = list(goal.get("order") or [])
    if want_order:
        observed = [n for n in move_order(agent_plan) if n in want_order]
        checks["order_matches"] = observed == want_order
    else:
        checks["order_matches"] = None

    # Route, when the task requires passing through a bin.
    want_visit = dict(goal.get("visit") or {})
    if want_visit:
        got = route(agent_plan)
        checks["visit_matches"] = all(
            all(zone in got.get(name, []) for zone in zones)
            for name, zones in want_visit.items())
    else:
        checks["visit_matches"] = None

    # Ordered route, when the exact sequence is graded.
    want_seq = dict(goal.get("visit_sequence") or {})
    if want_seq:
        got = route(agent_plan)
        checks["visit_sequence_matches"] = all(
            got.get(name, []) == list(seq) for name, seq in want_seq.items())
    else:
        checks["visit_sequence_matches"] = None

    applicable = [v for v in checks.values() if v is not None]
    return {
        "task_id": task_id,
        "template": spec["template_id"],
        "instruction": spec["instruction"],
        "planned": True,
        "agent_placement": got_placement,
        "expected_placement": want_placement,
        "agent_order": move_order(agent_plan),
        "expected_order": want_order or None,
        "agent_route": route(agent_plan),
        "expected_visit": want_visit or None,
        "agent_confidence": agent_plan.get("confidence"),
        "checks": checks,
        "plan_level_correct": all(applicable),
        "tokens": (reply.get("usage") or {}).get("tokens"),
    }


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) < 2:
        print("usage: check_plans.py <plan_dir> <task_id> [<task_id> ...]",
              file=sys.stderr)
        return 2
    plan_dir, task_ids = argv[0], argv[1:]
    rows = [check_one(plan_dir, t) for t in task_ids]
    correct = sum(1 for r in rows if r.get("plan_level_correct"))
    print(json.dumps({
        "__caveat__": ("PLAN-LEVEL ONLY. Not the independent evaluator, which grades "
                       "the final world state after execution. Not a held-out or "
                       "generalisation measurement: these are TRAIN instances."),
        "rows": rows,
        "plan_level_correct": correct,
        "instances": len(rows),
        "total_tokens": sum(r.get("tokens") or 0 for r in rows),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
