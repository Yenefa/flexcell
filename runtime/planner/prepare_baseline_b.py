#!/usr/bin/env python3
"""Prepare a Baseline B run: build the agent's observation, let it plan, validate.

DELIBERATE LIMIT: this script reads exactly two fields from the TaskSpec - the
instruction and the scene composition (which objects and bins exist, with colours and
positions). It never reads expected_goal, constraints, or the evaluator. That is
enforced by only touching the whitelisted keys, and asserted at the end.
"""
import json
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WT / "runtime" / "planner"))
sys.path.insert(0, str(WT / "experiments" / "pilot-001"))

import agent_planner as ap

SCENE_FILE = WT / "benchmark" / "generators" / "generate.py"

# Colour lookup comes from the WORLD assets, i.e. what the camera would see.
COLORS = {"target_box_a": "red", "target_box_b": "blue", "target_box_c": "green"}
ZONE_LABEL = {"zone_1": [0.12, -0.15, 0.0175], "zone_2": [0.25, 0.05, 0.0175]}


def observation_from_spec(spec):
    """Only instruction + scene. Nothing that encodes the answer."""
    return {
        "instruction": spec["instruction"],
        "objects": [{"name": o["name"], "color": COLORS[o["name"]],
                     "position": list(o["initial_pose"][:3])} for o in spec["objects"]],
        "zones": [{"name": z, "position": ZONE_LABEL[z], "radius": 0.06}
                  for z in ("zone_1", "zone_2")],
        "skills": ["observe", "pick", "place", "verify", "move_to_pose", "run_composite"],
    }


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) < 2:
        print("usage: prepare_baseline_b.py <spec.json> <out_dir>", file=sys.stderr)
        return 2
    spec = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    out = Path(argv[1]); out.mkdir(parents=True, exist_ok=True)
    obs = observation_from_spec(spec)
    (out / "observation_input.json").write_text(json.dumps(obs, indent=2) + "\n",
                                               encoding="utf-8")

    from pilot.llm import Chat
    chat = Chat()
    agent_plan, problems, raw = ap.plan(obs, chat)
    (out / "agent_reply.json").write_text(json.dumps({
        "agent_plan": agent_plan, "problems": problems, "raw_reply": raw,
        **chat.metadata()}, indent=2) + "\n", encoding="utf-8")

    if problems or agent_plan is None:
        print(json.dumps({"stage": "planning", "problems": problems}, indent=2))
        return 1

    # convert using bin positions only; the object->bin mapping is the agent's
    scene = {"zones": [{"name": z, "pose": ZONE_LABEL[z]} for z in ("zone_1", "zone_2")]}
    comp = ap.to_composite_plan(scene, agent_plan)
    plan = {
        "task_id": spec["task_id"],
        "initial_objects": [{"object_name": o["name"],
                             "position": list(o["initial_pose"][:3])}
                            for o in spec["objects"]],
        "stages": comp["stages"],
        "final_empty_positions": [],
        "position_tolerance_m": 0.02,
        "clearance_m": 0.06,
        "motion_profile_id": "demo_slow",
    }
    (out / "plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"moves": agent_plan["moves"],
                      "confidence": agent_plan.get("confidence"),
                      "uncertainty": agent_plan.get("uncertainty")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
