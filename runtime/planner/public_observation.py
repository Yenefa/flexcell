#!/usr/bin/env python3
"""Baseline B observation v2 -- a PURE FUNCTION of the public task.

WHY THIS EXISTS (three defects proved in the v1 builder, not suspected):

1. v1 is not a function of its input. `prepare_baseline_b.observation_from_spec`
   emits colours from a module constant `COLORS` and bin poses from a module
   constant `ZONE_LABEL`. Measured: mutating the task's own `color` and `zones[0]
   .pose` leaves the observation BYTE-IDENTICAL. So the agent is handed a
   hardcoded world, not the world it was asked about. It happens to match the
   default scene today, which is exactly why nobody noticed.

2. v1 emits bins the task does not declare. Measured on T02 and T03: the spec
   declares `["zone_1"]`, the observation emits `["zone_1", "zone_2"]`. That is
   an affordance leak in the opposite direction to the usual one -- the agent is
   told it may use a bin the task never offered, and a plan that uses it is not
   wrong-looking, it is ungradeable.

3. v1's docstring promises the safety property it does not have:
   "That is enforced by only touching the whitelisted keys, and asserted at the
   end." There is no assertion. Measured: `"assert "` does not appear in the
   module body at all. A comment claiming a check is worse than no comment,
   because the next reader stops looking.

THE PROPERTY THIS MODULE ENFORCES, structurally rather than by comment:

    build_observation() refuses to run at all unless its input carries ONLY
    public keys. It does not "avoid reading" expected_goal; it cannot be handed
    a dict containing expected_goal without raising.

That is checkable, mutation-testable, and it does not depend on me remembering.

WHAT THE AGENT MAY SEE, and why each item is not an answer:
    instruction        the natural-language goal -- the task itself
    objects            name / colour / measured pose -- perception
    zones              name / pose / radius -- perception of affordances
    skills             which primitives the robot has -- the toolbox
    budget             max_steps / max_wall_s -- a resource limit, not an answer
    frame_convention   "+y is the robot LEFT" -- a robot fact, like knowing
                       which of your hands is which; it does not say what to do

WHAT IT MUST NEVER SEE: expected_goal, constraints, template_id, random_seed,
instance_sha256. Those are the answer, the answer's structure, and the answer's
provenance respectively.
"""
import json

# The exact field set a PUBLIC task may carry. This is the same list
# benchmark/generators/seal_held_out.py produces, so a held-out public task and a
# train spec reduced to its public fields are accepted by the same function.
PUBLIC_KEYS = frozenset({
    "task_id", "instruction", "objects", "zones",
    "evaluator_version", "execution_budget", "split",
})

# Answer-bearing keys. Presence of ANY of these is a leak, not a warning.
ANSWER_KEYS = frozenset({
    "expected_goal", "constraints", "template_id", "random_seed",
    "instance_sha256", "placement", "unmoved", "visit", "visit_sequence",
    "order", "min_tiers", "relative",
})

# Skills are named, never ordered. The list is a toolbox, not a plan: it says
# "you may pick things up", not "pick A then B". Kept in one place so a test can
# cross-check it against the action definitions that actually exist on disk
# (src/flexcell/flexcell_interfaces/action/*.action) -- a skill name that no
# action backs would be an invented capability.
SKILLS = ("observe", "pick", "place", "verify", "move_to_pose", "run_composite")

# Frame convention: a robot fact, stated once. Without it "left"/"right" in an
# instruction is uninterpretable and the task would be testing telepathy.
FRAME_CONVENTION = "+y is the robot LEFT, -y is the robot RIGHT, +x is forward."


class LeakError(ValueError):
    """Raised when a task handed to the agent carries answer-bearing structure."""


def assert_public(task):
    """Refuse anything that is not a bare public task.

    Checked by KEY, not by scanning prose. Natural language is allowed to say
    "in this order"; a field named `order` is the answer. This mirrors the
    reasoning in benchmark/generators/seal_held_out.assert_public_is_clean,
    which was fixed after a prose scan rejected a legitimate instruction.
    """
    if not isinstance(task, dict):
        raise LeakError("task must be a dict, got %s" % type(task).__name__)
    leaked = sorted(set(task) & ANSWER_KEYS)
    if leaked:
        raise LeakError(
            "task carries answer-bearing keys %s -- the agent may not be given "
            "these, and this builder will not silently drop them" % leaked)
    unknown = sorted(set(task) - PUBLIC_KEYS)
    if unknown:
        raise LeakError(
            "task carries keys outside the public contract %s -- if one of these "
            "is legitimate, add it to PUBLIC_KEYS deliberately" % unknown)
    for required in ("instruction", "objects", "zones"):
        if required not in task:
            raise LeakError("task is missing required public field %r" % required)
    return True


def build_observation(task):
    """Return the observation dict handed to the planning model.

    Every value is read from `task`. There is no module-level table of colours,
    poses, or bin names, because a table is a place for a hardcoded world to
    hide -- and v1 hid one there for long enough to be reported as working.
    """
    assert_public(task)

    objects = []
    for obj in task["objects"]:
        objects.append({
            "name": obj["name"],
            "color": obj.get("color"),
            "position": [float(v) for v in obj["initial_pose"][:3]],
        })

    # EXACTLY the declared bins. Not the union with the default scene: a bin the
    # task never offered is not an affordance, it is a way to fail ungradeably.
    zones = []
    for zone in task["zones"]:
        zones.append({
            "name": zone["name"],
            "position": [float(v) for v in zone["pose"]],
            "radius": float(zone["radius"]),
        })

    budget = task.get("execution_budget") or {}
    return {
        "instruction": task["instruction"],
        "objects": objects,
        "zones": zones,
        "skills": list(SKILLS),
        "frame_convention": FRAME_CONVENTION,
        "budget": {
            "max_steps": budget.get("max_steps"),
            "max_wall_s": budget.get("max_wall_s"),
        },
    }


def reduce_to_public(spec):
    """Drop a full TaskSpec down to its public fields, then verify the result.

    Used for TRAIN instances, where the full spec is legitimately on disk. The
    reduction is explicit and the output is re-checked by assert_public, so a
    future spec field cannot ride along by default.
    """
    public = {k: json.loads(json.dumps(spec[k])) for k in PUBLIC_KEYS if k in spec}
    assert_public(public)
    return public


def main(argv=None):
    import sys
    from pathlib import Path
    argv = argv or sys.argv[1:]
    if len(argv) < 2:
        print("usage: public_observation.py <public_or_train_task.json> <out.json>",
              file=sys.stderr)
        return 2
    task = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    if "expected_goal" in task:
        task = reduce_to_public(task)
    obs = build_observation(task)
    out = Path(argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(obs, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"objects": len(obs["objects"]), "zones": len(obs["zones"]),
                      "budget": obs["budget"]}, indent=2))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
