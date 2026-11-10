#!/usr/bin/env python3
"""EvoBot Baseline A-prime — deterministic rule planner, FAIR like-for-like.

WHY THIS EXISTS: the original Baseline A read `expected_goal` from the spec, which is
an oracle planner - it cannot fail on planning, so comparing it to the agent measured
execution reliability, not planning. That is a broken comparison and I am calling it
out rather than reporting the numbers it produced as if they meant something.

A-prime gets EXACTLY the same input as Baseline B: the instruction, the objects it can
see, and the bins. It has no LLM. It parses the instruction with fixed rules and
applies fixed geometry. Whatever it cannot parse, it cannot do - which is the honest
measure of a deterministic FSM baseline.
"""
import re
import sys
from pathlib import Path

COLOR_WORD = {"red": "red", "blue": "blue", "green": "green"}
BIN_WORD = {"right": "zone_1", "left": "zone_2", "1": "zone_1", "2": "zone_2"}


def _by_color(observation, word):
    for o in observation["objects"]:
        if o["color"] == word:
            return o
    return None


def _bin(word):
    return BIN_WORD.get(word.strip().lower())


def plan(observation):
    """Return {"moves": [...]} or raise Unparsed. Deterministic, no model."""
    text = observation["instruction"]
    lower = text.lower()
    objects = observation["objects"]

    # Rule 1: exclusion - "except the <colour> block"
    m = re.search(r"except the (\w+) block", lower)
    if m and "clear the table" in lower:
        keep = _by_color(observation, m.group(1))
        zone = _bin(re.search(r"into the (\w+) bin", lower).group(1))
        moves = [{"object": o["name"], "zone": zone, "why": "rule:exclusion"}
                 for o in objects if o["name"] != keep["name"]]
        return {"moves": moves, "rule": "exclusion"}

    # Rule 2: geometric discrimination - "FURTHER from the robot base"
    if "further from the robot base" in lower:
        import math
        dist = {o["name"]: math.hypot(o["position"][0], o["position"][1]) for o in objects}
        names = sorted(dist, key=lambda n: dist[n])
        near, far = names[0], names[-1]
        right = _bin(re.search(r"into the (\w+) bin", lower).group(1))
        left = _bin(re.search(r"nearer block into the (\w+) bin", lower).group(1))
        return {"moves": [{"object": far, "zone": right, "why": "rule:distance"},
                          {"object": near, "zone": left, "why": "rule:distance"}],
                "rule": "geometric"}

    # Rule 3: ordered list - "in this order: the red, then the blue"
    if "in this order" in lower:
        tail = lower.split("in this order", 1)[1]
        colors = re.findall(r"the (\w+)", tail)
        zone = _bin(re.search(r"into the (\w+) bin", lower).group(1))
        moves = []
        for c in colors:
            o = _by_color(observation, c)
            if o is None:
                raise Unparsed("unknown colour in order list: " + c)
            moves.append({"object": o["name"], "zone": zone, "why": "rule:order"})
        return {"moves": moves, "rule": "ordered"}

    # Rule 4: two assignments - "the red block in the right bin and the blue in the left"
    pairs = re.findall(r"the (\w+) block in the (\w+) bin", lower)
    if len(pairs) >= 2:
        moves = []
        for color, side in pairs:
            o = _by_color(observation, color)
            z = _bin(side)
            if o is None or z is None:
                raise Unparsed("cannot resolve %r -> %r" % (color, side))
            moves.append({"object": o["name"], "zone": z, "why": "rule:assignment"})
        return {"moves": moves, "rule": "assignment"}

    raise Unparsed("no rule matches this instruction")


class Unparsed(Exception):
    pass


def main(argv=None):
    import json
    argv = argv or sys.argv[1:]
    obs = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    try:
        result = plan(obs)
    except Unparsed as exc:
        print(json.dumps({"unparsed": str(exc)}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
