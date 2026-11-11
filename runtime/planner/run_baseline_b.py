#!/usr/bin/env python3
"""Baseline B end-to-end harness: task -> observation -> agent plan -> plan.json.

THIS RUNS THE PLANNING HALF ONLY. It does not start Gazebo, does not move the
robot, and does not grade anything. Execution is a separate, serialised step
(one simulator at a time) and grading belongs to the independent evaluator.

WHAT IT PROVES WHEN IT SUCCEEDS
    The agent produced a structurally executable plan for a task it was given
    only the instruction and a perception of the scene. Nothing more. A plan is
    not a success: only the evaluator can say whether the world ended up right.

WHAT IT REFUSES TO DO
    - read expected_goal / constraints / template_id / random_seed (the reducer
      raises if they are present, and a test asserts the raised path)
    - read benchmark/held_out/ or benchmark/evaluators/ -- an explicit guard
      below fails the run if either path is opened
    - obtain a model credential by any route other than the budget gate

COST: every run calls the model once. At the measured 728-971 tokens per plan
and the account balance recorded in the gate audit log, one instance is a
fraction of a fen. --dry makes ZERO model calls and is the default for tests.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime" / "planner"))

import agent_planner_v2 as ap
import public_observation as po

# Paths the agent runtime must never open. Kept as a list so the guard below and
# the test that checks the guard both read the same source of truth.
FORBIDDEN_PREFIXES = ("benchmark/held_out", "benchmark/evaluators")


class IsolationError(RuntimeError):
    """The harness tried to touch a path the agent runtime must not read."""


def assert_not_forbidden(path):
    """Refuse to read an answer-bearing path. Called before every read below."""
    resolved = str(Path(path).resolve()).replace("\\", "/")
    for prefix in FORBIDDEN_PREFIXES:
        marker = "/" + prefix + "/"
        if marker in resolved + "/" or resolved.endswith("/" + prefix):
            raise IsolationError(
                "refusing to read %s: it is under %s, which the agent runtime must "
                "not read (see benchmark/README.md, hard rule)" % (path, prefix))
    return True


def read_task(path):
    assert_not_forbidden(path)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def to_executor_plan(task_public, observation, agent_plan):
    """Assemble the plan.json the composite client will dispatch.

    Bin POSITIONS come from the observation (i.e. from the task's public scene).
    The object->bin mapping, the move order, and every intermediate hop come from
    the agent. spread_destinations only de-overlaps landings that share a bin; it
    never changes which bin, so it cannot leak or invent an answer.
    """
    composite = ap.to_composite_plan(observation["zones"], agent_plan)
    moved = {stage["object_name"] for stage in composite["stages"]}
    avoid = [[obj["position"][0], obj["position"][1]]
             for obj in observation["objects"] if obj["name"] not in moved]

    sys.path.insert(0, str(ROOT / "experiments" / "baselines"))
    import spread_destinations as sd

    stages = sd.spread(composite["stages"], avoid=avoid)

    # clearance_m must sit inside the RunComposite contract window 0.05..0.25.
    # Derived from the observed object size, not hardcoded: 1.3x the box edge is
    # physically justified for non-overlap, and the contract floor applies when
    # that is smaller (35 mm boxes -> 45.5 mm -> floored to 50 mm).
    edge = max(float(o.get("size", [0.035])[0]) if o.get("size") else 0.035
               for o in task_public.get("objects", [{"size": [0.035]}]))
    clearance = min(0.25, max(0.05, round(1.3 * edge, 4)))

    return {
        "task_id": task_public["task_id"],
        "initial_objects": [{"object_name": obj["name"],
                             "position": list(obj["position"])}
                            for obj in observation["objects"]],
        "stages": stages,
        "final_empty_positions": [],
        "position_tolerance_m": 0.02,
        "clearance_m": clearance,
        "motion_profile_id": "demo_slow",
    }


def run_one(task_path, out_dir, dry=False, chat=None):
    """Plan one instance. Returns a result dict; never raises on a bad plan."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    raw_task = read_task(task_path)
    task_public = po.reduce_to_public(raw_task) if "expected_goal" in raw_task else raw_task
    observation = po.build_observation(task_public)
    (out / "observation_input.json").write_text(
        json.dumps(observation, indent=2) + "\n", encoding="utf-8")

    result = {"task_id": task_public["task_id"], "dry": dry,
              "instruction": observation["instruction"]}

    if dry:
        system, user = ap.build_prompt(observation)
        (out / "prompt.txt").write_text(system + "\n\n---\n\n" + user, encoding="utf-8")
        result.update({"planned": False, "stage": "dry", "tokens": 0})
        (out / "result.json").write_text(json.dumps(result, indent=2) + "\n",
                                        encoding="utf-8")
        return result

    if chat is None:
        from gated_chat import GatedChat
        chat = GatedChat(caller="baseline-b-harness")

    try:
        agent_plan, raw_reply, usage = ap.plan(observation, chat)
    except (ap.PlanRejected, ValueError) as exc:
        result.update({"planned": False, "stage": "planning",
                       "problems": getattr(exc, "problems", [str(exc)])})
        # The raw reply is written even on failure. Without it a rejection cannot be
        # told apart from a model error, and a lost failure is a lost result.
        (out / "agent_reply.json").write_text(json.dumps({
            "agent_plan": None, "problems": result["problems"],
            "raw_reply": getattr(exc, "raw_reply", ""),
            "usage": getattr(exc, "usage", {}),
            **chat.metadata()}, indent=2) + "\n", encoding="utf-8")
        (out / "result.json").write_text(json.dumps(result, indent=2) + "\n",
                                        encoding="utf-8")
        return result

    (out / "agent_reply.json").write_text(json.dumps({
        "agent_plan": agent_plan, "problems": [], "raw_reply": raw_reply,
        "usage": usage, **chat.summary()}, indent=2) + "\n", encoding="utf-8")

    plan = to_executor_plan(task_public, observation, agent_plan)
    (out / "plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")

    result.update({"planned": True, "stage": "planned",
                   "moves": agent_plan["moves"],
                   "unmoved": agent_plan["unmoved"],
                   "confidence": agent_plan.get("confidence"),
                   "stages": len(plan["stages"]),
                   "tokens": usage.get("tokens"),
                   "model": usage.get("model"),
                   "key_fingerprint": chat.metadata().get("key_fingerprint")})
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n",
                                    encoding="utf-8")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tasks", nargs="+", help="public or train task JSON files")
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument("--dry", action="store_true",
                        help="build prompts only; makes ZERO model calls")
    args = parser.parse_args(argv)

    summaries = []
    for index, task_path in enumerate(args.tasks):
        name = Path(task_path).stem
        result = run_one(task_path, Path(args.out) / name, dry=args.dry)
        summaries.append(result)
        print(json.dumps({k: result.get(k) for k in
                          ("task_id", "stage", "planned", "moves", "tokens",
                           "problems")}, indent=2))

    planned = sum(1 for r in summaries if r.get("planned"))
    print(json.dumps({"instances": len(summaries), "planned": planned,
                      "total_tokens": sum(r.get("tokens") or 0 for r in summaries),
                      "dry": args.dry}, indent=2))
    return 0 if args.dry or planned == len(summaries) else 1


if __name__ == "__main__":
    sys.exit(main())
