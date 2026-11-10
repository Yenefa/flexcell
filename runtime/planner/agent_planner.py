#!/usr/bin/env python3
"""EvoBot Baseline B — the agent plans the task itself.

DIFFERENCE FROM BASELINE A: A was handed a stage list derived mechanically from the
spec. B is handed only what a robot could actually perceive plus the instruction, and
must decide what to move, where, and in what order.

WHAT THE AGENT SEES
  - the instruction (same text a human would give)
  - the objects it can see: name, colour, position
  - the bins it can see: name, position
  - the skills it may call

WHAT THE AGENT NEVER SEES
  - expected_goal, constraints, or the spec itself
  - the evaluator, its tolerances, or its verdicts
  - held-out instances

This module is only the planner: it returns a proposed plan and a validation result.
It never grades itself, and a plan it produces is not evidence of anything until the
independent evaluator has seen the resulting world state.
"""
import json
import sys
from pathlib import Path

MAX_STAGES = 8

SYSTEM = """You are the planning component of a robot workcell.
You receive a task instruction, the objects the robot can see, and the bins it can use.
Return a plan: an ordered list of moves. Each move names one object and the bin it
must end up in.

Rules you must respect:
- Only use object names and bin names that appear in the observation.
- The instruction may tell you to leave something alone; do not plan a move for it.
- If the instruction fixes an order, follow it exactly.
- At most 8 moves.
- Two objects may look alike; use their measured positions to tell them apart.

Reply with JSON only, no prose:
{"moves":[{"object":"<name>","zone":"<bin name>","why":"<short reason>"}],
 "unmoved":["<object names you deliberately leave alone>"],
 "confidence":"high|medium|low",
 "uncertainty":"<one sentence, or empty>"}"""


def describe(observation):
    """Render the observation as text. Colour is a perceived property, not a hint."""
    lines = ["Robot frame: +y is the robot LEFT, -y is the robot RIGHT, +x is forward."]
    for o in observation["objects"]:
        x, y = o["position"][0], o["position"][1]
        lines.append("  %s  colour=%s  at x=%.3f y=%.3f" % (o["name"], o["color"], x, y))
    lines.append("Bins I can use:")
    for z in observation["zones"]:
        x, y = z["position"][0], z["position"][1]
        lines.append("  %s  at x=%.3f y=%.3f  radius=%.3f" % (z["name"], x, y, z["radius"]))
    lines.append("Skills available: " + ", ".join(observation["skills"]))
    return "\n".join(lines)


def build_prompt(observation):
    return (SYSTEM, describe(observation) + "\n\nTask instruction:\n"
            + observation["instruction"] + "\n\nReturn JSON only.")


def parse_reply(text):
    """Extract the JSON object from a model reply, tolerating code fences."""
    t = text.strip()
    if "```" in t:
        parts = t.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                t = p
                break
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in reply")
    return json.loads(t[start:end + 1])


def validate_plan(reply, observation):
    """Structural checks only. Whether the plan is CORRECT is the evaluator's job."""
    problems = []
    known_objects = {o["name"] for o in observation["objects"]}
    known_zones = {z["name"] for z in observation["zones"]}
    moves = reply.get("moves")
    if not isinstance(moves, list) or not moves:
        return None, ["plan has no moves"]
    if len(moves) > MAX_STAGES:
        problems.append("plan has %d moves, the executor allows %d"
                        % (len(moves), MAX_STAGES))
    clean = []
    for i, m in enumerate(moves):
        if not isinstance(m, dict):
            problems.append("move %d is not an object" % i)
            continue
        obj, zone = m.get("object"), m.get("zone")
        if obj not in known_objects:
            problems.append("move %d names unknown object %r" % (i, obj))
        if zone not in known_zones:
            problems.append("move %d names unknown bin %r" % (i, zone))
        if obj in known_objects and zone in known_zones:
            clean.append({"object": obj, "zone": zone, "why": str(m.get("why", ""))[:200]})
    unmoved = reply.get("unmoved")
    if unmoved is not None and not isinstance(unmoved, list):
        problems.append("unmoved must be a list")
    # Repeated object names are DELIBERATELY allowed: RunComposite documents support
    # for them, and a relay task is exactly the case where one object is moved twice.
    # An earlier version of this validator rejected such plans, which would have made a
    # correct relay plan look like a malformed one.
    moved = [c["object"] for c in clean]
    if not moved:
        problems.append("no valid moves after validation")
    return {"moves": clean, "unmoved": list(unmoved or []),
            "confidence": reply.get("confidence"),
            "uncertainty": str(reply.get("uncertainty", ""))[:300]}, problems


def plan(observation, chat):
    """Ask the model for a plan and validate it. Returns (plan, problems, raw)."""
    system, user = build_prompt(observation)
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": user}]
    response = chat.chat(messages)
    # The client returns (content, usage-ish dict); accept both shapes so a change
    # in the client does not silently produce an empty plan.
    if isinstance(response, tuple):
        raw = response[0]
    elif isinstance(response, dict):
        raw = response.get("content") or ""
    else:
        raw = str(response)
    reply = parse_reply(raw)
    plan_obj, problems = validate_plan(reply, observation)
    return plan_obj, problems, raw


def to_composite_plan(spec_for_poses, agent_plan):
    """Convert an agent plan into the executor plan.

    NOTE: only bin POSITIONS come from the scene, never the expected placement. The
    mapping object -> bin is entirely the agent's.
    """
    zones = {z["name"]: z["pose"] for z in spec_for_poses["zones"]}
    stages = []
    for i, m in enumerate(agent_plan["moves"]):
        stages.append({"stage_id": "%s-%d" % (m["object"], i),
                       "object_name": m["object"],
                       "place_pose": list(zones[m["zone"]])})
    return {"stages": stages}


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) < 2:
        print("usage: agent_planner.py <observation.json> <out.plan.json> [--dry]",
              file=sys.stderr)
        return 2
    obs = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    out = Path(argv[1])
    if "--dry" in argv:
        system, user = build_prompt(obs)
        print(user)
        return 0
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "experiments" / "pilot-001"))
    from pilot.llm import Chat
    chat = Chat()
    agent_plan, problems, raw = plan(obs, chat)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"agent_plan": agent_plan, "problems": problems,
                               "raw_reply": raw, **chat.metadata()}, indent=2) + "\n",
                   encoding="utf-8")
    print(json.dumps({"problems": problems,
                      "moves": None if agent_plan is None else agent_plan["moves"]},
                     indent=2))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
