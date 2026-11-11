#!/usr/bin/env python3
"""Tests that the deterministic baseline cannot see the answer, and does solve the templates.

WHY BOTH DIRECTIONS: this baseline exists to make a NEGATIVE claim credible - that the benchmark
cannot show the LLM is necessary. That claim is only valid if the parser is honest (no answer
access) and competent (it really does produce correct plans). A parser that peeked would prove
nothing; a parser that was merely broken would prove the opposite of what is claimed.
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "rp", ROOT / "runtime" / "planner" / "rule_planner.py")
RP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RP)

OBS = {
    "objects": [
        {"name": "target_box_a", "color": "red", "position": [0.22, 0.0, 0.0175]},
        {"name": "target_box_b", "color": "blue", "position": [0.2, -0.18, 0.0175]},
    ],
    "zones": [
        {"name": "zone_1", "position": [0.12, -0.15, 0.0175], "radius": 0.06},
        {"name": "zone_2", "position": [0.25, 0.05, 0.0175], "radius": 0.06},
    ],
    "skills": ["observe", "pick", "place", "verify", "move_to_pose"],
}


def _obs(instruction):
    o = dict(OBS)
    o["instruction"] = instruction
    return o


def test_left_is_derived_from_measured_y_not_from_a_name_table():
    """+y is the robot LEFT, so zone_2 (y=0.05) must be 'left' and zone_1 (y=-0.15) 'right'."""
    left, right = RP._by_side(OBS["zones"])
    assert left["name"] == "zone_2"
    assert right["name"] == "zone_1"


def test_the_order_template_is_parsed_with_the_required_sequence():
    moves, _, note = RP.plan(_obs(
        "Put both blocks in the left bin. The blue block must be put there FIRST, then the "
        "red block. Doing it in the other order is not acceptable even if both end up in "
        "the right bin. Do not move anything else."))
    assert [(m["object"], m["zone"]) for m in moves] == [
        ("target_box_b", "zone_2"), ("target_box_a", "zone_2")], note


def test_the_relay_template_yields_three_moves_not_four():
    """The instruction names a bin a fourth time in its trailing sentence; that is not a move."""
    moves, unmoved, note = RP.plan(_obs(
        "Put the red block in the left bin, then move it to the right bin, then put it back "
        "in the left bin. It must actually visit the right bin. Leave the other block "
        "exactly where it is."))
    assert len(moves) == 3, (len(moves), note)
    assert [m["zone"] for m in moves] == ["zone_2", "zone_1", "zone_2"]
    assert unmoved == ["target_box_b"]


def test_the_conditional_branch_follows_the_measured_distance():
    moves, _, note = RP.plan(_obs(
        "Compare distances before moving: if the red block is closer to the left bin than "
        "to the right bin, put BOTH blocks in the right bin; otherwise put BOTH blocks in "
        "the left bin. Do not guess from the colours."))
    # red sits 58.3 mm from the left bin and 180.3 mm from the right one, so the branch
    # selects the RIGHT bin, i.e. zone_1
    assert {m["zone"] for m in moves} == {"zone_1"}, note


def test_an_unparseable_instruction_declines_instead_of_guessing():
    moves, _, note = RP.plan(_obs("Weld the two blocks together."))
    assert moves == []
    assert "declined" in note


def test_the_planner_never_reads_the_answer():
    src = (ROOT / "runtime" / "planner" / "rule_planner.py").read_text(encoding="utf-8")
    for forbidden in ("expected_goal", "sealed", "instance_sha256", "constraints",
                      "evaluate", "verdict"):
        assert not re.search(r"[\"']%s[\"']" % forbidden, src), forbidden
