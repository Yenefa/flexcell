#!/usr/bin/env python3
"""Tests pinning the release-failure mechanism and the pre-registration discipline.

WHY: the first actuator-stall proposal was written on an assumption the logs refute - that a
failed release meant the object had not been released. Nine records across two batches all
show carry_release_confirmed=True alongside released=False. Re-commanding a release that
already happened cannot help, so the proposal had to be superseded rather than implemented.

These tests exist so the correction cannot quietly disappear.
"""
import glob
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROP = ROOT / "evolution" / "proposals"


def _release_failures():
    for base in ("/tmp/evobot-batch2", "/tmp/evobot-batch3"):
        for d in sorted(glob.glob(os.path.join(base, "HO-*"))):
            p = os.path.join(d, "sim", "skills", "place.jsonl")
            if not os.path.exists(p):
                continue
            for line in open(p, encoding="utf-8", errors="replace"):
                line = line.strip()
                if not line:
                    continue
                x = json.loads(line)
                if not x.get("released"):
                    yield d, x


def test_every_release_failure_confirmed_the_carry_release():
    seen = 0
    for d, x in _release_failures():
        seen += 1
        assert x.get("carry_release_confirmed") is True, (
            d, "a release failure where the carry layer did NOT confirm release would "
               "refute the mechanism")
    if seen:
        assert seen == 9, seen


def test_every_release_failure_is_a_gripper_stall_not_a_missing_release():
    for d, x in _release_failures():
        g = x.get("gripper_open") or {}
        assert g.get("reached_goal") is False, d
        assert g.get("classification") == "GRASP_STALLED", d
        assert "did not open" in str(x.get("detail")), d


def test_the_superseded_proposal_states_why_it_could_not_be_implemented():
    doc = json.loads((PROP / "actuator_stall_preregistration.json").read_text(
        encoding="utf-8"))
    sb = doc["superseded_basis"]
    assert "false failure" in (sb["why"] + sb["measured"]).lower()
    assert "NOT APPROVED" in sb["status_of_this_preregistration"]


def test_the_new_proposal_is_registered_and_unapproved():
    doc = json.loads((PROP / "release_confirmation_preregistration.json").read_text(
        encoding="utf-8"))
    assert doc["requires_human_approval"] is True
    assert doc["approved"] is False, "an agent must never approve its own proposal"
    assert doc["registered_before_change"] is True


def test_the_new_proposal_predicts_within_the_honesty_rules():
    doc = json.loads((PROP / "release_confirmation_preregistration.json").read_text(
        encoding="utf-8"))
    # the pass rate may not fall, and no success may be invented
    assert "must not fall" in doc["prediction"]["final_pass_rate"].lower()
    joined = " ".join(doc["refutation_criteria"]).lower()
    assert "does not satisfy the goal" in joined
    assert "false success" in joined
    assert doc["anti_gaming"]["evaluator_untouched"] is True


def test_the_skill_layer_was_not_modified_this_round():
    """The proposal is not implemented; the place server still fails on aperture alone."""
    doc = json.loads((PROP / "release_confirmation_preregistration.json").read_text(
        encoding="utf-8"))
    assert "not implemented" in doc["status"].lower()
    assert doc["approved"] is False
