#!/usr/bin/env python3
"""Baseline A-prime: a DETERMINISTIC rule planner over the same observation as baseline B.

WHY THIS EXISTS: baseline B is an LLM and it scores well, but "well" only means something if a
non-learning baseline would not also score well. Baseline A from the original track read
expected_goal, which made it an open-book oracle and therefore not a baseline at all. This one
reads exactly what B reads - the instruction, the visible objects, the visible bins - and
parses it with rules fixed in advance.

WHAT IT MEASURES: how much of the benchmark a simple parser already solves. If a deterministic
parser matches the LLM, the LLM's measurable value on these templates is zero, and saying
otherwise would be attributing to the agent what a regular expression did.

NO ANSWER ACCESS: nothing here reads expected_goal, constraints, the spec, or a verdict. The
left/right direction comes from the measured geometry (+y is the robot LEFT), not from a lookup
table of zone names - the robot has to derive it the same way.
"""
import json
import re


def _by_side(zones):
    """Map 'left'/'right' to zone names using MEASURED y, not a hardcoded table."""
    left = max(zones, key=lambda z: z["position"][1])
    right = min(zones, key=lambda z: z["position"][1])
    return left, right


def _colour_map(objects):
    return {str(o.get("color", "")).lower(): o["name"] for o in objects}


def _side_to_zone(word, zones):
    left, right = _by_side(zones)
    return left["name"] if word.startswith("l") else right["name"]


def plan(observation):
    """Return (moves, unmoved, note). Deterministic; no model, no randomness."""
    text = str(observation.get("instruction") or "")
    objects = observation.get("objects") or []
    zones = observation.get("zones") or []
    colours = _colour_map(objects)
    moves = []
    unmoved = []
    note = ""

    # ---- T14: "The <colour> block must be put there FIRST, then the <colour> block."
    m_first = re.search(r"the (\w+) block must be put there first", text, re.I)
    if m_first:
        bins = re.findall(r"in the (\w+) bin", text, re.I)
        zone = _side_to_zone(bins[0], zones) if bins else None
        first = colours.get(m_first.group(1).lower())
        m_then = re.search(r"then the (\w+) block", text, re.I)
        second = colours.get(m_then.group(1).lower()) if m_then else None
        if zone and first and second:
            moves = [{"object": first, "zone": zone,
                      "why": "required first by the instruction"},
                     {"object": second, "zone": zone,
                      "why": "required second by the instruction"}]
            return moves, unmoved, "T14 order parsed"

    # ---- T13: conditional on measured distance
    m_if = re.search(
        r"if the (\w+) block is closer to the (left|right) bin than to the (left|right) bin,\s*"
        r"put both blocks in the (left|right) bin", text, re.I)
    if m_if:
        colour, near_word, far_word, target_word = (
            m_if.group(1).lower(), m_if.group(2).lower(),
            m_if.group(3).lower(), m_if.group(4).lower())
        name = colours.get(colour)
        if name:
            pose = next(o["position"] for o in objects if o["name"] == name)
            left, right = _by_side(zones)
            def dist(z):
                return ((pose[0] - z["position"][0]) ** 2
                        + (pose[1] - z["position"][1]) ** 2) ** 0.5
            d_near = dist(left if near_word == "left" else right)
            d_far = dist(left if far_word == "left" else right)
            branch_left = target_word == "left"
            if d_near < d_far:
                chosen = branch_left
            else:
                chosen = not branch_left
            zone = left["name"] if chosen else right["name"]
            moves = [{"object": o["name"], "zone": zone,
                      "why": "conditional resolved from measured distance"}
                     for o in objects]
            return moves, unmoved, "T13 conditional resolved"

    # ---- T12: three clauses, parsed STRUCTURALLY
    # The instruction names the bins four times when the trailing "it must actually visit"
    # sentence is counted. Extracting every "the <side> bin" therefore produced FOUR moves
    # where the task needs three, which understated this baseline. The sentence structure
    # ("put ... in X, then move it to Y, then put it back in X") is what carries the plan.
    m_t12 = re.search(
        r"put the (\w+) block in the (\w+) bin,\s*then move it to the (\w+) bin,\s*"
        r"then put it back in the (\w+) bin", text, re.I)
    if m_t12:
        colour = m_t12.group(1).lower()
        name = colours.get(colour)
        sides = [m_t12.group(2).lower(), m_t12.group(3).lower(),
                 m_t12.group(4).lower()]
        if name and all(x in ("left", "right") for x in sides):
            moves = [{"object": name, "zone": _side_to_zone(x, zones),
                      "why": "relay step %d" % (i + 1)} for i, x in enumerate(sides)]
            others = [o["name"] for o in objects if o["name"] != name]
            return moves, others, "T12 relay parsed structurally"

    # ---- generic: "put both blocks in the <side> bin"
    m_both = re.search(r"put both blocks in the (\w+) bin", text, re.I)
    if m_both and m_both.group(1).lower() in ("left", "right"):
        zone = _side_to_zone(m_both.group(1).lower(), zones)
        moves = [{"object": o["name"], "zone": zone, "why": "both blocks"}
                 for o in objects]
        return moves, unmoved, "generic both-blocks rule"

    return [], [], "no rule matched - declined"
