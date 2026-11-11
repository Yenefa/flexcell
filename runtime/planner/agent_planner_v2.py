#!/usr/bin/env python3
"""Baseline B planner v2 -- the agent decides WHAT moves WHERE, in WHAT ORDER.

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------
This is the runtime agent arm. It is handed an observation (see
public_observation.py) and it returns a plan. It is NOT handed a stage list, a
template name, a skill order, or any file/line to change. The only thing that
distinguishes Baseline A from Baseline B is that A's object->bin mapping is
derived mechanically from expected_goal while B's is inferred by a model from
natural language plus perception.

WHY A SECOND PLANNER EXISTS AT ALL
----------------------------------
agent_planner.py (v1) works, is unit-tested, and produced the verified T01
result. This module does not replace it and does not delete it. It fixes three
things v1 cannot express, all measured, not suspected:

1. V1 CANNOT PLAN AN ORDER OR A ROUTE. Its reply schema is
   {"moves":[{"object","zone"}]} and to_composite_plan emits stages in list
   order with one stage per move. But T03 is graded on the "order" clause, and
   T05 is graded on the "visit" clause -- a relay through an intermediate bin.
   V1's validate_plan explicitly ALLOWS a repeated object ("a relay needs
   them"), yet nothing in the schema can express WHICH intermediate bin, and
   the evaluator's visit clause needs exactly that. So a correct relay is not
   expressible in v1's contract: the plan is accepted and then cannot be
   graded as a relay.
   Here a move carries "via": the intermediate bins to pass through, in order.

2. V1 VALIDATES STRUCTURE ONLY, AND SILENTLY DROPS. validate_plan appends a
   problem for an unknown object and then CONTINUES, returning a "clean" list
   that has quietly lost a move. A caller that only checks "if problems" is
   fine; a caller that logs problems and proceeds gets a truncated plan.
   Worse, v1 never checks the plan against the ORDER the instruction asked for,
   so an order-violating plan validates clean.
   Here: every violation is fatal, and nothing is dropped.

3. V1 HAS NO BUDGET AWARENESS. execution_budget.max_steps is in the spec and is
   never consulted. A plan longer than the budget is a guaranteed failure that
   looks like a robot failure.
   Here: the plan is rejected if its stage count exceeds the declared budget.

NO-LEAK DISCIPLINE, STATED AS A TEST
------------------------------------
The prompt is built from the observation ONLY. A test asserts that the rendered
prompt contains no answer-bearing key and no object/bin pairing -- because the
v1 prompt was checked the same way and the check is what keeps it honest.

The system prompt describes the OUTPUT CONTRACT, which is interface, not answer.
It never says which object goes to which bin, and it never names a template.
"""
import json

MAX_STAGES = 8
MAX_VIA = 2

SYSTEM = """You are the planning component of a robot workcell.
You receive a task instruction, the objects the robot can see, the bins it may use,
and a step budget. Return a plan.

A plan is an ordered list of moves. Each move names:
  object  - the object to move (a name from the observation)
  zone    - the bin it must end up in (a name from the observation)
  via     - OPTIONAL. Bins this object must be placed into on the way, in order,
            before reaching zone. Use it only if the instruction asks for an
            intermediate stop. Omit it otherwise.

Rules you must respect:
- Only use object names and bin names that appear in the observation.
- If the instruction says to leave something alone, do not plan a move for it.
- If the instruction fixes an order, list the moves in that order.
- The same object may appear more than once only when the instruction moves it
  more than once.
- Do not exceed the step budget you were given.
- Some objects look alike; use their measured positions to tell them apart.
- The instruction is in English and refers to left/right in the ROBOT frame given
  to you.

Reply with JSON only, no prose:
{"moves":[{"object":"<name>","zone":"<bin>","via":["<bin>"],"why":"<short reason>"}],
 "unmoved":["<object names you deliberately leave alone>"],
 "confidence":"high|medium|low",
 "uncertainty":"<one sentence, or empty>"}"""


def describe(observation):
    """Render the observation as text. Perception and interface only."""
    lines = ["Robot frame: " + observation.get(
        "frame_convention",
        "+y is the robot LEFT, -y is the robot RIGHT, +x is forward.")]
    lines.append("Objects I can see:")
    for obj in observation["objects"]:
        x, y, z = obj["position"][0], obj["position"][1], obj["position"][2]
        lines.append("  %s  colour=%s  at x=%.3f y=%.3f z=%.3f"
                     % (obj["name"], obj.get("color"), x, y, z))
    lines.append("Bins I may use:")
    for zone in observation["zones"]:
        x, y = zone["position"][0], zone["position"][1]
        lines.append("  %s  at x=%.3f y=%.3f  radius=%.3f"
                     % (zone["name"], x, y, zone["radius"]))
    lines.append("Skills available: " + ", ".join(observation["skills"]))
    budget = observation.get("budget") or {}
    if budget.get("max_steps"):
        lines.append("Step budget: at most %d moves." % int(budget["max_steps"]))
    return "\n".join(lines)


def build_prompt(observation):
    return (SYSTEM, describe(observation) + "\n\nTask instruction:\n"
            + observation["instruction"] + "\n\nReturn JSON only.")


def parse_reply(text):
    """Extract the JSON object from a model reply, tolerating code fences."""
    body = (text or "").strip()
    if "```" in body:
        for part in body.split("```"):
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                body = part
                break
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in reply")
    return json.loads(body[start:end + 1])


class PlanRejected(ValueError):
    """The reply was structurally unusable. Fatal, never partially applied."""

    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = list(problems)


def validate_plan(reply, observation):
    """Structural checks only. Whether the plan is CORRECT is the evaluator's job.

    Every failure is collected and raised together, so a caller sees all of them
    at once instead of fixing one per run. Nothing is silently dropped: unlike v1,
    a move that names an unknown object does NOT disappear into a shorter plan.
    """
    problems = []
    known_objects = {o["name"] for o in observation["objects"]}
    known_zones = {z["name"] for z in observation["zones"]}
    budget = (observation.get("budget") or {}).get("max_steps")
    limit = MAX_STAGES if not budget else min(MAX_STAGES, int(budget))

    if not isinstance(reply, dict):
        raise PlanRejected(["reply is not a JSON object"])
    moves = reply.get("moves")
    if not isinstance(moves, list) or not moves:
        raise PlanRejected(["plan has no moves"])
    if len(moves) > limit:
        problems.append("plan has %d moves, the limit is %d (max_stages=%d, "
                        "declared budget=%s)"
                        % (len(moves), limit, MAX_STAGES, budget))

    clean, seen_pairs = [], set()
    for index, move in enumerate(moves):
        if not isinstance(move, dict):
            problems.append("move %d is not an object" % index)
            continue
        obj, zone = move.get("object"), move.get("zone")
        if obj not in known_objects:
            problems.append("move %d names unknown object %r" % (index, obj))
        if zone not in known_zones:
            problems.append("move %d names unknown bin %r" % (index, zone))
        via = move.get("via") or []
        if not isinstance(via, list):
            problems.append("move %d: via must be a list of bin names" % index)
            via = []
        if len(via) > MAX_VIA:
            problems.append("move %d: at most %d intermediate bins, got %d"
                            % (index, MAX_VIA, len(via)))
        for hop in via:
            if hop not in known_zones:
                problems.append("move %d: unknown intermediate bin %r" % (index, hop))
        if via and via[-1] == zone:
            problems.append("move %d: the last intermediate bin repeats the "
                            "destination %r, which is not a relay" % (index, zone))
        pair = (obj, zone, tuple(via))
        if pair in seen_pairs:
            problems.append("move %d repeats an earlier identical move" % index)
        seen_pairs.add(pair)
        if obj in known_objects and zone in known_zones and all(
                hop in known_zones for hop in via):
            clean.append({"object": obj, "zone": zone, "via": list(via),
                          "why": str(move.get("why", ""))[:200]})

    unmoved = reply.get("unmoved")
    if unmoved is not None and not isinstance(unmoved, list):
        problems.append("unmoved must be a list")
    for name in (unmoved or []):
        if name not in known_objects:
            problems.append("unmoved names unknown object %r" % (name,))

    # An object moved twice (relay / revisit) has exactly ONE final destination:
    # the zone of the LAST move naming it. The evaluator grades the final state
    # only, so this is the same reading it uses.
    #
    # THE BUG THIS REPLACES, found by a real run and not by reasoning: the first
    # version collected every zone per object into a SET and rejected the plan if
    # the set had more than one member. That rejected a CORRECT revisit. The model
    # encodes a revisit two equally valid ways --
    #     one move with via:  {"object": a, "zone": zone_1, "via": [zone_2]}
    #     two sequential moves: {"object": a, "zone": zone_2}, {"object": a, "zone": zone_1}
    # -- and only the first survived. On a 18-instance sweep this cost 1 instance
    # (T06-train-seed1001): a plan that would have been graded correct was thrown
    # away by the validator, which is a false NEGATIVE and looks like a planning
    # failure. Rejecting a legal encoding is as wrong as accepting an illegal one.
    final_zone = {}
    for move in clean:
        final_zone[move["object"]] = move["zone"]
    # A `via` hop that is also a later final destination is not contradictory, but a
    # via hop that is the LAST hop before a different final zone is dead weight: it
    # costs a full pick-and-place and changes nothing the evaluator reads.
    for obj, zone in final_zone.items():
        hops = [hop for move in clean if move["object"] == obj
                for hop in (move.get("via") or [])]
        for hop in hops:
            if hop == zone:
                problems.append(
                    "object %r is routed through %r and also finishes there, which "
                    "costs a pick-and-place and changes nothing the task grades"
                    % (obj, zone))

    if not clean:
        problems.append("no valid moves after validation")
    if problems:
        raise PlanRejected(problems)

    return {"moves": clean,
            "unmoved": list(unmoved or []),
            "confidence": reply.get("confidence"),
            "uncertainty": str(reply.get("uncertainty", ""))[:300]}


def plan(observation, chat):
    """Ask the model for a plan. Returns (plan, raw, usage).

    Raises PlanRejected on an unusable reply and ValueError on unparseable JSON.
    It never returns a partial plan: a caller cannot accidentally execute one.
    """
    system, user = build_prompt(observation)
    response = chat.chat([{"role": "system", "content": system},
                          {"role": "user", "content": user}])
    raw = response.get("content", "") if isinstance(response, dict) else str(response)
    usage = {k: response.get(k) for k in ("tokens", "seconds", "model")} \
        if isinstance(response, dict) else {}
    # Attach the raw reply to the exception. A rejection without the model's actual
    # words is unfalsifiable: the first sweep lost the reply for the one instance
    # that failed, so "the validator rejected it" could not be checked against
    # "the model was wrong". That is the difference between a bug and a result.
    try:
        reply = parse_reply(raw)
        validated = validate_plan(reply, observation)
    except (PlanRejected, ValueError) as exc:
        exc.raw_reply = raw
        exc.usage = usage
        raise
    return validated, raw, usage


def _zone_position(zone):
    """Return a zone's [x, y, z] from EITHER shape this codebase uses.

    The planner's observation calls it "position"; a TaskSpec calls it "pose".
    Both are correct in their own layer, and the first version of
    to_composite_plan assumed "pose" -- so every call that passed an observation
    raised KeyError, and the harness test caught it before the robot did. Rather
    than force one caller to reshape, accept both and be explicit about it: a
    silent default here would be a coordinate bug, which is the most expensive
    kind to find later.
    """
    for key in ("position", "pose"):
        if key in zone:
            value = zone[key]
            if len(value) != 3:
                raise ValueError("zone %r has a %d-element %s, expected 3"
                                 % (zone.get("name"), len(value), key))
            return [float(v) for v in value]
    raise ValueError("zone %r carries neither 'position' nor 'pose'"
                     % (zone.get("name"),))


def to_composite_plan(scene_zones, agent_plan):
    """Convert an agent plan into the executor's stage list.

    Only bin POSITIONS come from the scene. The object->bin mapping, the order of
    the moves, and every intermediate hop come from the agent. A relay becomes two
    stages for the same object -- which RunComposite documents as legal ("Repeated
    object names are allowed" in CompositeStage.msg) -- in the order the agent
    gave, not in an order derived from the bins.
    """
    poses = {z["name"]: _zone_position(z) for z in scene_zones}
    stages = []
    for index, move in enumerate(agent_plan["moves"]):
        for hop_index, hop in enumerate(move.get("via") or []):
            stages.append({"stage_id": "%s-via%d-%d" % (move["object"], hop_index, index),
                           "object_name": move["object"],
                           "place_pose": poses[hop]})
        stages.append({"stage_id": "%s-%d" % (move["object"], index),
                       "object_name": move["object"],
                       "place_pose": poses[move["zone"]]})
    return {"stages": stages}


def main(argv=None):
    import sys
    from pathlib import Path
    argv = argv or sys.argv[1:]
    if len(argv) < 2:
        print("usage: agent_planner_v2.py <observation.json> <out.json> [--dry]",
              file=sys.stderr)
        return 2
    observation = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    if "--dry" in argv:
        system, user = build_prompt(observation)
        print(user)
        return 0
    from gated_chat import GatedChat, GateRefused
    try:
        chat = GatedChat(caller="baseline-b-planner")
    except GateRefused as exc:
        print(json.dumps({"stage": "credential", "error": str(exc)}))
        return 3
    raw = ""
    try:
        validated, raw, usage = plan(observation, chat)
    except (PlanRejected, ValueError) as exc:
        out = {"agent_plan": None,
               "problems": getattr(exc, "problems", [str(exc)]),
               "raw_reply": raw,
               **chat.summary()}
        Path(argv[1]).parent.mkdir(parents=True, exist_ok=True)
        Path(argv[1]).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"stage": "planning", "problems": out["problems"]}, indent=2))
        return 1
    out = {"agent_plan": validated, "problems": [], "raw_reply": raw,
           "usage": usage, **chat.summary()}
    Path(argv[1]).parent.mkdir(parents=True, exist_ok=True)
    Path(argv[1]).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"moves": validated["moves"],
                      "confidence": validated.get("confidence"),
                      "tokens": usage.get("tokens")}, indent=2))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
