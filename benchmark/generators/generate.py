#!/usr/bin/env python3
"""EvoBot task generator v0.1.

Produces reproducible TaskSpec instances from (template_id, seed). The same pair
always yields the same spec, so a held-out instance can be regenerated for
re-checking without ever shipping the answer to the agent.

SCOPE, stated honestly: T01-T06 are implemented against the CURRENT workcell
(three 35 mm boxes, two bins, 4-DOF arm + gripper, ~380 mm reach). T07-T10 need
physical skills that do not exist yet and are registered as NOT_IMPLEMENTED
rather than emitted with invented expectations.
"""
import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

GENERATOR_VERSION = "0.1.0"
EVALUATOR_VERSION = "0.1.0"

# Measured from the worlds the smoke harness actually generates.
#
# IMPORTANT: the DEFAULT world contains only box_a and box_b. target_box_c exists
# as a standalone asset (worlds/target_box_c.sdf) and only appears in the
# three_boxes scene, which is a different profile. Declaring c here made every
# RunComposite plan fail with "plan must declare every observed object", because the
# robot observes two boxes and the plan claimed three. Scene composition is a
# property of the WORLD, not of the task, so it is recorded per scene.
SCENES = {
    "default": {"objects": ["target_box_a", "target_box_b"],
                "zones": ["zone_1", "zone_2"]},
    "three_boxes": {"objects": ["target_box_a", "target_box_b", "target_box_c"],
                    "zones": ["zone_1", "zone_2"]},
}

OBJECTS = {
    "target_box_a": {"color": "red", "pose": [0.220, 0.000, 0.0175, 0.0]},
    "target_box_b": {"color": "blue", "pose": [0.200, -0.180, 0.0175, 0.0]},
    "target_box_c": {"color": "green", "pose": [0.150, -0.050, 0.0175, 0.0]},
}

DEFAULT_SCENE = "default"
BOX_SIZE = [0.035, 0.035, 0.035]
# +y is the robot left (ROS REP-103), so zone_2 (y>0) is "left".
ZONES = {
    "zone_1": {"pose": [0.12, -0.15, 0.0175], "radius": 0.06, "label": "right"},
    "zone_2": {"pose": [0.25, 0.05, 0.0175], "radius": 0.06, "label": "left"},
}

NOT_IMPLEMENTED = {
    "T07_stacking": "needs a stacking skill; nothing can place on top of a box yet",
    "T08_push": "needs a non-grasping push primitive",
    "T09_clutter": "needs distractors placed without collisions",
    "T10_constrained_placement": "needs a constrained-scene variant",
}


def _objects_for(names):
    """Every object that exists in the scene.

    This is deliberately the full scene set, not just the objects the task asks
    to move: an object that must NOT move still has to be declared, otherwise the
    evaluator has no initial pose to compare against and cannot tell whether it
    stayed put.
    """
    return [{"name": n, "size": list(BOX_SIZE), "color": OBJECTS[n]["color"],
             "initial_pose": list(OBJECTS[n]["pose"])} for n in sorted(names)]


def _zones_for(names):
    return [{"name": z, "pose": list(ZONES[z]["pose"]), "radius": ZONES[z]["radius"]}
            for z in names]


def _scene_objects(split):
    return list(SCENES[DEFAULT_SCENE]["objects"])


def _label(zone):
    return ZONES[zone]["label"]


def _spec(template, seed, split, instruction, names, zone_names, placement,
          unmoved=None, order=None, min_tiers=None, max_steps=40, max_wall_s=600):
    goal = {"placement": placement, "unmoved": list(unmoved or [])}
    if order:
        goal["order"] = list(order)
    if min_tiers:
        goal["min_tiers"] = int(min_tiers)
    return {
        "task_id": "%s-%s-seed%04d" % (template.split("_")[0], split.replace("_", ""), seed),
        "template_id": template,
        "random_seed": int(seed),
        "instruction": instruction,
        "objects": _objects_for(names),
        "zones": _zones_for(zone_names),
        "constraints": {"order": list(order or []), "must_not_move": list(unmoved or [])},
        "expected_goal": goal,
        "evaluator_version": EVALUATOR_VERSION,
        "execution_budget": {"max_steps": int(max_steps), "max_wall_s": float(max_wall_s)},
        "split": split,
    }


def t01_multi_object_sorting(seed, split):
    rng = random.Random(seed)
    names = sorted(rng.sample(_scene_objects(split), 2))
    first, second = names
    placement = {first: "zone_1", second: "zone_2"}
    instruction = "Put the %s block in the %s bin and the %s block in the %s bin." % (
        OBJECTS[first]["color"], _label("zone_1"),
        OBJECTS[second]["color"], _label("zone_2"))
    unmoved = [n for n in _scene_objects(split) if n not in names]
    return _spec("T01_multi_object_sorting", seed, split, instruction,
                 _scene_objects(split), ["zone_1", "zone_2"], placement, unmoved=unmoved)


def t02_exclusion(seed, split):
    rng = random.Random(seed)
    names = _scene_objects(split)
    keep = rng.choice(names)
    move = [n for n in names if n != keep]
    placement = {n: "zone_1" for n in move}
    instruction = "Clear the table into the %s bin, except the %s block, which must stay put." % (
        _label("zone_1"), OBJECTS[keep]["color"])
    return _spec("T02_exclusion", seed, split, instruction, names, ["zone_1"],
                 placement, unmoved=[keep])


def t03_ordered(seed, split):
    rng = random.Random(seed)
    names = sorted(rng.sample(_scene_objects(split), min(3, len(_scene_objects(split)))))
    order = list(names)
    rng.shuffle(order)
    placement = {n: "zone_1" for n in names}
    sentence = ", then the ".join(OBJECTS[n]["color"] for n in order)
    instruction = "Move blocks into the %s bin in this order: the %s." % (
        _label("zone_1"), sentence)
    return _spec("T03_ordered", seed, split, instruction, names, ["zone_1"],
                 placement, order=order, max_steps=60)


def t04_duplicates(seed, split):
    names = ["target_box_a", "target_box_b"]
    first, second = names
    placement = {first: "zone_1", second: "zone_2"}
    instruction = "Two blocks look alike. Put the one further from the robot in the %s bin, the nearer one in the %s bin." % (
        _label("zone_1"), _label("zone_2"))
    return _spec("T04_duplicates", seed, split, instruction, names,
                 ["zone_1", "zone_2"], placement)


def t05_relay(seed, split):
    rng = random.Random(seed)
    name = rng.choice(_scene_objects(split))
    others = [n for n in _scene_objects(split) if n != name]
    placement = {name: "zone_2"}
    instruction = "Move the %s block to the %s bin, passing through the %s bin first." % (
        OBJECTS[name]["color"], _label("zone_2"), _label("zone_1"))
    return _spec("T05_relay", seed, split, instruction, _scene_objects(split),
                 ["zone_1", "zone_2"], placement, unmoved=others, max_steps=50)


def t06_revisit(seed, split):
    rng = random.Random(seed)
    name = rng.choice(_scene_objects(split))
    others = [n for n in _scene_objects(split) if n != name]
    placement = {name: "zone_1"}
    instruction = "Two-step: put the %s block in the %s bin, then move it on to the %s bin. Only the final position counts." % (
        OBJECTS[name]["color"], _label("zone_2"), _label("zone_1"))
    return _spec("T06_revisit", seed, split, instruction, _scene_objects(split),
                 ["zone_1", "zone_2"], placement, unmoved=others, max_steps=60)


TEMPLATES = {
    "T01_multi_object_sorting": t01_multi_object_sorting,
    "T02_exclusion": t02_exclusion,
    "T03_ordered": t03_ordered,
    "T04_duplicates": t04_duplicates,
    "T05_relay": t05_relay,
    "T06_revisit": t06_revisit,
}


def generate(template_id, seed, split="train"):
    if template_id in NOT_IMPLEMENTED:
        raise NotImplementedError(template_id + ": " + NOT_IMPLEMENTED[template_id])
    if template_id not in TEMPLATES:
        raise KeyError("unknown template " + repr(template_id))
    spec = TEMPLATES[template_id](int(seed), split)
    blob = json.dumps(spec, sort_keys=True).encode("utf-8")
    spec["instance_sha256"] = hashlib.sha256(blob).hexdigest()
    return spec


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True,
                    choices=sorted(list(TEMPLATES) + list(NOT_IMPLEMENTED)))
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--split", default="train", choices=["train", "val", "held_out"])
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    try:
        spec = generate(args.template, args.seed, args.split)
    except NotImplementedError as exc:
        print("NOT_IMPLEMENTED: " + str(exc), file=sys.stderr)
        return 2
    text = json.dumps(spec, indent=2) + "\n"
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print("wrote " + args.out)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
