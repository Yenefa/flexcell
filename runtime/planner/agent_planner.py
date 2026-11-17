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
import re

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
    # Baseline C only. Experience is a list of VALIDATED planner-level lessons
    # retrieved from archived failures. It contains no task answer: the scope guard
    # in the experience store rejects any lesson naming an evaluator, tolerance or
    # grading rule, and a test asserts the enriched observation has no answer fields.
    lessons = observation.get("experience") or []
    if lessons:
        lines.append("Validated lessons from earlier failures (process hints, not answers):")
        for item in lessons:
            lines.append("  - [%s] %s" % (item.get("failure_class", "UNKNOWN"),
                                          item.get("lesson", "")))
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


# The instruction's own ordering clause. This is NOT a grading rule - the evaluator owns
# whether a plan is correct, and this module must never see a tolerance or a verdict. It is
# the planner checking itself against a rule the SYSTEM PROMPT already tells it to follow:
#   "If the instruction fixes an order, follow it exactly."
# Until this existed that sentence was advice nobody checked. The archive holds one plan that
# reversed a required order; it was found only after a full run, because validate_plan only
# looked at whether the names were known.
_ORDER_FIRST = re.compile(r"the (\w+) block must be put there FIRST", re.I)


def _required_first(observation):
    """Which object the instruction says must be moved first, or None if it says nothing."""
    text = str((observation or {}).get("instruction") or "")
    m = _ORDER_FIRST.search(text)
    if not m:
        return None
    colour = m.group(1).lower()
    for obj in (observation or {}).get("objects") or []:
        if str(obj.get("color", "")).lower() == colour:
            return obj.get("name")
    return None


def check_plan_order(observation, moves):
    """Return a problem string when the plan reverses an order the instruction fixed.

    WHY A PLAN-SIDE CHECK AND NOT ANOTHER EVALUATOR CLAUSE: the evaluator already grades
    'order', but only AFTER the robot has moved. A plan that reverses the order is knowable
    before execution, and rejecting it then costs nothing while running it costs a run.
    """
    required = _required_first(observation)
    if not required or not moves:
        return None
    first = moves[0].get("object")
    if first == required:
        return None
    moved = [m.get("object") for m in moves]
    if required not in moved:
        return None  # the required object is not moved at all; that is a different fault
    return ("the instruction requires %r to be moved FIRST, but the plan starts with %r"
            % (required, first))


def validate_plan(reply, observation):
    """Structural checks plus the instruction's own order clause.

    Whether the plan is CORRECT is still the evaluator's job: this only refuses a plan that
    contradicts a rule the instruction states explicitly.
    """
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
    order_problem = check_plan_order(observation, clean)
    if order_problem:
        problems.append(order_problem)
    return {"moves": clean, "unmoved": list(unmoved or []),
            "confidence": reply.get("confidence"),
            "uncertainty": str(reply.get("uncertainty", ""))[:300]}, problems


def plan(observation, chat):
    """Ask the model for a plan. Returns (plan, problems, raw, usage)."""
    system, user = build_prompt(observation)
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": user}]
    response = chat.chat(messages)
    # The client returns a dict with content AND usage. Keep the usage: resource cost
    # must be reported per arm, otherwise a budget advantage can masquerade as a
    # capability advantage (experiment protocol rule 1).
    if isinstance(response, dict):
        raw = response.get("content") or ""
    elif isinstance(response, tuple):
        raw = response[0]
    else:
        raw = str(response)
    reply = parse_reply(raw)
    plan_obj, problems = validate_plan(reply, observation)
    usage = {k: response.get(k) for k in ("tokens", "seconds", "model")} \
        if isinstance(response, dict) else {}
    return plan_obj, problems, raw, usage


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


if __name__ == "__main__":
    raise SystemExit("Research CLI moved to experiments/baselines/plan_v1.py; this module provides reusable planning functions.")
