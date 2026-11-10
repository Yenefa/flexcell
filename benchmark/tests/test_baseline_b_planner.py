#!/usr/bin/env python3
"""Baseline B planner tests: the contract, the guards, and the no-leak property.

No network here. The model is stubbed so these test MY code, not how some model
happens to answer today.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime" / "planner"))

import agent_planner as ap

INSTRUCTION = "Put the red block in the right bin and the blue block in the left bin."


def _obs(instruction=INSTRUCTION):
    return {
        "instruction": instruction,
        "objects": [
            {"name": "target_box_a", "color": "red", "position": [0.22, 0.0, 0.0175]},
            {"name": "target_box_b", "color": "blue", "position": [0.20, -0.18, 0.0175]},
        ],
        "zones": [
            {"name": "zone_1", "position": [0.12, -0.15, 0.0175], "radius": 0.06},
            {"name": "zone_2", "position": [0.25, 0.05, 0.0175], "radius": 0.06},
        ],
        "skills": ["observe", "pick", "place", "verify", "run_composite"],
    }


class StubChat:
    def __init__(self, reply):
        self.reply = reply if isinstance(reply, str) else json.dumps(reply)

    def chat(self, messages, tools=None, tool_choice=None):
        assert messages[-1]["role"] == "user"
        return self.reply, {"tokens": 0}

    def metadata(self):
        return {"model": "stub"}


def test_prompt_contains_what_the_robot_can_perceive():
    system, user = ap.build_prompt(_obs())
    assert "target_box_a" in user and "target_box_b" in user
    assert "zone_1" in user and "zone_2" in user
    assert "colour=red" in user and "colour=blue" in user
    assert "Put the red block" in user
    assert "+y is the robot LEFT" in user


def test_prompt_never_contains_the_answer():
    """The observation half must carry only perception; the schema half is interface.

    "unmoved" is a generic output field that exists for every task - it does not say
    WHICH object to leave alone - so it is allowed in the schema. It must NOT appear
    in the part built from the scene, because there it would be a hint.
    """
    system, user = ap.build_prompt(_obs())
    low_user = user.lower()
    for leak in ["expected", "placement", "evaluator", "tolerance",
                 "correct plan", "solution", "unmoved"]:
        assert leak not in low_user, leak
    low_system = system.lower()
    for leak in ["expected", "placement", "evaluator", "tolerance", "target_box"]:
        assert leak not in low_system, leak


def test_observation_carries_no_hint_about_which_object_goes_where():
    # The bins are named and located; nothing pairs an object with a bin.
    system, user = ap.build_prompt(_obs())
    for line in user.splitlines():
        has_object = "target_box_" in line
        has_zone = "zone_" in line
        assert not (has_object and has_zone), line


def test_valid_plan_is_accepted():
    reply = {"moves": [{"object": "target_box_a", "zone": "zone_1", "why": "right bin"},
                       {"object": "target_box_b", "zone": "zone_2", "why": "left bin"}],
             "unmoved": [], "confidence": "high", "uncertainty": ""}
    plan_obj, problems, _ = ap.plan(_obs(), StubChat(reply))
    assert problems == []
    assert [m["object"] for m in plan_obj["moves"]] == ["target_box_a", "target_box_b"]


def test_unknown_object_or_bin_is_rejected():
    reply = {"moves": [{"object": "target_box_c", "zone": "zone_9"}], "unmoved": []}
    plan_obj, problems, _ = ap.plan(_obs(), StubChat(reply))
    assert problems
    assert any("unknown object" in p for p in problems)
    assert any("unknown bin" in p for p in problems)


def test_more_than_eight_moves_is_rejected():
    reply = {"moves": [{"object": "target_box_a", "zone": "zone_1"}] * 9, "unmoved": []}
    plan_obj, problems, _ = ap.plan(_obs(), StubChat(reply))
    assert any("allows 8" in p for p in problems), problems


def test_duplicate_object_is_rejected():
    reply = {"moves": [{"object": "target_box_a", "zone": "zone_1"},
                       {"object": "target_box_a", "zone": "zone_2"}], "unmoved": []}
    plan_obj, problems, _ = ap.plan(_obs(), StubChat(reply))
    assert any("more than once" in p for p in problems)


def test_json_inside_a_code_fence_is_parsed():
    fenced = "```json\n" + json.dumps(
        {"moves": [{"object": "target_box_a", "zone": "zone_1"}], "unmoved": []}) + "\n```"
    plan_obj, problems, _ = ap.plan(_obs(), StubChat(fenced))
    assert problems == [], problems
    assert plan_obj["moves"][0]["object"] == "target_box_a"


def test_garbage_reply_raises_rather_than_silently_passing():
    with pytest.raises(ValueError):
        ap.plan(_obs(), StubChat("I think the red block should go left."))


def test_composite_conversion_takes_bin_positions_from_the_scene():
    scene = {"zones": [{"name": "zone_1", "pose": [0.12, -0.15, 0.0175]},
                       {"name": "zone_2", "pose": [0.25, 0.05, 0.0175]}]}
    plan_obj = {"moves": [{"object": "target_box_a", "zone": "zone_2"}]}
    comp = ap.to_composite_plan(scene, plan_obj)
    assert comp["stages"][0]["place_pose"] == [0.25, 0.05, 0.0175]
    assert comp["stages"][0]["object_name"] == "target_box_a"

