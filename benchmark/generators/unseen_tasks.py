#!/usr/bin/env python3
"""EvoBot v0.2 UNSEEN task types.

WHY A SEPARATE MODULE: v0.1 (T01-T06) is frozen and its held-out answers are sealed.
Adding templates to that generator would change every split and break the seal mapping.
This module is additive: it produces genuinely different task TYPES that the agent has
never been trained on, with their own sealed answers.

The point of these templates is HEADROOM. On v0.1 Baseline B passes 6/6 held-out, so no
experiment can show whether experience helps. These types require longer-horizon state
tracking and measurement-based branching, which the deterministic rule engine cannot do
at all and which a model may get wrong.

They still use ONLY existing physical primitives (pick/place/verify) and the current
2-box 2-bin scene. No new skill, no changed evaluator, no injected defect.
"""
import hashlib
import json
import math
import random
from pathlib import Path

OBJECTS = {
    "target_box_a": {"color": "red", "pose": [0.220, 0.000, 0.0175, 0.0]},
    "target_box_b": {"color": "blue", "pose": [0.200, -0.180, 0.0175, 0.0]},
}
BOX_SIZE = [0.035, 0.035, 0.035]
ZONES = {"zone_1": {"pose": [0.12, -0.15, 0.0175], "radius": 0.06, "label": "right"},
         "zone_2": {"pose": [0.25, 0.05, 0.0175], "radius": 0.06, "label": "left"}}
SCENE_OBJECTS = ["target_box_a", "target_box_b"]
EVALUATOR_VERSION = "0.1.0"


def _dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _spec(template, seed, split, instruction, placement, unmoved=None, visit=None,
          visit_sequence=None, order=None, max_steps=60):
    goal = {"placement": placement, "unmoved": list(unmoved or [])}
    if visit:
        goal["visit"] = {k: list(v) for k, v in visit.items()}
    if visit_sequence:
        goal["visit_sequence"] = {k: list(v) for k, v in visit_sequence.items()}
    if order:
        goal["order"] = list(order)
    spec = {
        "task_id": "%s-%s-seed%04d" % (template.split("_")[0], split.replace("_", ""), seed),
        "template_id": template,
        "random_seed": int(seed),
        "instruction": instruction,
        "objects": [{"name": n, "size": list(BOX_SIZE), "color": OBJECTS[n]["color"],
                     "initial_pose": list(OBJECTS[n]["pose"])} for n in SCENE_OBJECTS],
        "zones": [{"name": z, "pose": list(ZONES[z]["pose"]),
                   "radius": ZONES[z]["radius"]} for z in ("zone_1", "zone_2")],
        "constraints": {"order": list(order or []), "must_not_move": list(unmoved or [])},
        "expected_goal": goal,
        "evaluator_version": EVALUATOR_VERSION,
        "execution_budget": {"max_steps": int(max_steps), "max_wall_s": 900.0},
        "split": split,
    }
    spec["instance_sha256"] = hashlib.sha256(
        json.dumps(spec, sort_keys=True).encode()).hexdigest()
    return spec


def t12_triple_revisit(seed, split):
    """Three moves of ONE object: right -> left -> right. Long-horizon state tracking.

    A model that only reads the final clause will go straight to the destination; that
    fails the visit clause. A model that loses track after two moves fails placement.
    """
    rng = random.Random(seed)
    name = rng.choice(SCENE_OBJECTS)
    other = [n for n in SCENE_OBJECTS if n != name][0]
    color = OBJECTS[name]["color"]
    instruction = ("Put the %s block in the %s bin, then move it to the %s bin, "
                   "then put it back in the %s bin. It must actually visit the %s bin. "
                   "Leave the other block exactly where it is." % (
                       color, ZONES["zone_1"]["label"], ZONES["zone_2"]["label"],
                       ZONES["zone_1"]["label"], ZONES["zone_2"]["label"]))
    return _spec("T12_triple_revisit", seed, split, instruction,
                 placement={name: "zone_1"}, unmoved=[other],
                 visit={name: ["zone_2"]},
                 visit_sequence={name: ["zone_1", "zone_2", "zone_1"]},
                 max_steps=70)


def t13_geometric_conditional(seed, split):
    """Destination depends on a MEASURED geometric comparison.

    The instruction states a conditional over distances from the block to the two bins.
    The correct branch is computed from the declared initial poses - the same geometry
    the agent can measure. This is not a fixed answer per seed: which branch applies is
    determined by the world, and a wrong measurement picks the wrong bin for BOTH
    objects.
    """
    rng = random.Random(seed)
    probe = rng.choice(SCENE_OBJECTS)
    color = OBJECTS[probe]["color"]
    d_left = _dist(OBJECTS[probe]["pose"], ZONES["zone_2"]["pose"])
    d_right = _dist(OBJECTS[probe]["pose"], ZONES["zone_1"]["pose"])
    closer_to_left = d_left < d_right
    if closer_to_left:
        target = "zone_1"
        reason_word = "nearer to the left bin"
    else:
        target = "zone_2"
        reason_word = "nearer to the right bin"
    placement = {n: target for n in SCENE_OBJECTS}
    instruction = ("Compare distances before moving: if the %s block is closer to the "
                   "left bin than to the right bin, put BOTH blocks in the right bin; "
                   "otherwise put BOTH blocks in the left bin. Do not guess from the "
                   "colours." % color)
    spec = _spec("T13_geometric_conditional", seed, split, instruction,
                 placement, max_steps=70)
    # kept private to this module; never emitted into the public task
    spec["_branch_note"] = reason_word
    return spec


def t14_ordered_pair(seed, split):
    """Two placements under a TEMPORAL constraint: one block must be put away first.

    WHY THIS TEMPLATE EXISTS: T12 asks for a repeated route and T13 asks for a measured
    choice, so every held-out instance so far varied only the WORLD, never the STRUCTURE of
    the requirement. A planner can satisfy both without ever reasoning about when things
    must happen. This one makes order part of the goal: the same final placement is correct
    only if the blocks were moved in the required sequence.

    The evaluator already grades this from move_sequence (clause "order"), so no evaluator
    change is needed and the ruler is untouched.
    """
    rng = random.Random(seed)
    names = list(SCENE_OBJECTS)
    first = rng.choice(names)
    second = [n for n in names if n != first][0]
    zone = rng.choice(["zone_1", "zone_2"])
    placement = {first: zone, second: zone}
    instruction = (
        "Put both blocks in the %s bin. The %s block must be put there FIRST, then the %s "
        "block. Doing it in the other order is not acceptable even if both end up in the "
        "right bin. Do not move anything else." % (
            ZONES[zone]["label"], OBJECTS[first]["color"], OBJECTS[second]["color"]))
    return _spec("T14_ordered_pair", seed, split, instruction, placement,
                 order=[first, second], max_steps=80)


TEMPLATES = {
    "T12_triple_revisit": t12_triple_revisit,
    "T13_geometric_conditional": t13_geometric_conditional,
    "T14_ordered_pair": t14_ordered_pair,
}


def generate(template_id, seed, split="held_out"):
    if template_id not in TEMPLATES:
        raise KeyError("unknown unseen template " + repr(template_id))
    return TEMPLATES[template_id](int(seed), split)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True, choices=sorted(TEMPLATES))
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--split", default="held_out")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    spec = generate(args.template, args.seed, args.split)
    text = json.dumps(spec, indent=2) + "\n"
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print("wrote " + args.out)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
