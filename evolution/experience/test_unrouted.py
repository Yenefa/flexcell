#!/usr/bin/env python3
"""Tests for the unrouted analysis: is UNROUTED a fact or a shrug?

WHY THIS EXISTS
    postmortem.generate() refuses 7 of 9 signatures as UNROUTED, covering 92 of the 98
    failures in the archive. The message reads "no consumer in this stack declares a change
    for X, so the knowledge would be stored and unable to act" - which is a statement about
    THIS STACK'S SIGNATURE TABLE, not about whether a module could act on the failure.

    Reading it as "nothing here can act" converts unwritten work into a measured limit. The
    objective already records the mirror-image error: route_lessons.py injected a
    landing-coordinate lesson into a planner that emits object->zone, and the plan came out
    identical. The lesson was true and the address was wrong. Both errors come from not
    asking which module's OUTPUT would actually change.
"""
import json
import os
import sys

import pytest

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import unrouted  # noqa: E402


@pytest.fixture(scope="module")
def report():
    return unrouted.report()


# ---------------------------------------------------------------- the distance clause

def test_the_expected_bin_follows_the_instruction_both_ways():
    """if blue is closer to the LEFT bin -> put BOTH in the RIGHT bin; otherwise LEFT.

    Getting the branches backwards would make the probe agree with a wrong plan, which is
    the worst possible failure for a check like this.
    """
    near_left = {"instruction": "Compare distances before moving: if the blue block is "
                                "closer to the left bin than to the right bin, put BOTH "
                                "blocks in the right bin; otherwise put BOTH blocks in the "
                                "left bin.",
                 "objects": [{"name": "a", "color": "red", "position": [0.2, 0.0]},
                             {"name": "b", "color": "blue", "position": [0.13, -0.14]}],
                 "zones": [{"name": "left", "position": [0.12, -0.15]},
                           {"name": "right", "position": [0.25, 0.05]}]}
    assert unrouted._expected_bin(near_left) == "right"

    near_right = json.loads(json.dumps(near_left))
    near_right["objects"][1]["position"] = [0.24, 0.04]
    assert unrouted._expected_bin(near_right) == "left"


def test_an_unrelated_instruction_has_no_expected_bin():
    assert unrouted._expected_bin(
        {"instruction": "Move the blue block to the left bin.",
         "objects": [], "zones": []}) is None


def test_the_probe_scores_a_wrong_plan_as_wrong(tmp_path):
    """The probe must be able to FAIL, or it is decoration."""
    root = tmp_path / "acc" / "batch" / "HO-x"
    root.mkdir(parents=True)
    (root / "observation_input.json").write_text(json.dumps({
        "instruction": "Compare distances before moving: put BOTH blocks in the right bin.",
        "objects": [{"name": "a", "color": "red", "position": [0.2, 0.0]},
                    {"name": "b", "color": "blue", "position": [0.13, -0.14]}],
        "zones": [{"name": "left", "position": [0.12, -0.15]},
                  {"name": "right", "position": [0.25, 0.05]}]}), encoding="utf-8")
    # blue is closer to the left bin, so BOTH must go RIGHT; this plan sends them LEFT
    (root / "agent_reply.json").write_text(json.dumps({
        "agent_plan": {"moves": [{"object": "a", "zone": "left"},
                                 {"object": "b", "zone": "left"}]}}), encoding="utf-8")
    result = unrouted.probe_planner_object_set({"HO-x"}, str(tmp_path / "acc"))
    assert result["instances_checked"] == 1
    assert result["instances_wrong"] == 1


def test_the_probe_scores_a_correct_plan_as_correct(tmp_path):
    root = tmp_path / "acc" / "batch" / "HO-y"
    root.mkdir(parents=True)
    (root / "observation_input.json").write_text(json.dumps({
        "instruction": "Compare distances before moving: put BOTH blocks in the right bin.",
        "objects": [{"name": "a", "color": "red", "position": [0.2, 0.0]},
                    {"name": "b", "color": "blue", "position": [0.13, -0.14]}],
        "zones": [{"name": "left", "position": [0.12, -0.15]},
                  {"name": "right", "position": [0.25, 0.05]}]}), encoding="utf-8")
    (root / "agent_reply.json").write_text(json.dumps({
        "agent_plan": {"moves": [{"object": "a", "zone": "right"},
                                 {"object": "b", "zone": "right"}]}}), encoding="utf-8")
    result = unrouted.probe_planner_object_set({"HO-y"}, str(tmp_path / "acc"))
    assert result["instances_wrong"] == 0


def test_a_plan_that_omits_an_object_is_wrong(tmp_path):
    """The clause says BOTH blocks. A plan that moves one of them does not satisfy it, and
    scoring it correct would credit the planner with work it did not do."""
    root = tmp_path / "acc" / "batch" / "HO-z"
    root.mkdir(parents=True)
    (root / "observation_input.json").write_text(json.dumps({
        "instruction": "Compare distances before moving: put BOTH blocks in the right bin.",
        "objects": [{"name": "a", "color": "red", "position": [0.2, 0.0]},
                    {"name": "b", "color": "blue", "position": [0.13, -0.14]}],
        "zones": [{"name": "left", "position": [0.12, -0.15]},
                  {"name": "right", "position": [0.25, 0.05]}]}), encoding="utf-8")
    (root / "agent_reply.json").write_text(json.dumps({
        "agent_plan": {"moves": [{"object": "a", "zone": "right"}]}}), encoding="utf-8")
    assert unrouted.probe_planner_object_set({"HO-z"}, str(tmp_path / "acc"))[
        "instances_wrong"] == 1


# ---------------------------------------------------------------- the report

def test_every_unrouted_signature_is_itemised(report):
    assert report["unrouted"]
    for row in report["unrouted"]:
        assert row["signature"]
        assert row["occurrences"]
        assert row["generator_said"].startswith("UNROUTED")


def test_only_the_scoreable_signature_is_given_a_verdict(report):
    """A selection effect must not become a verdict, so exactly one signature is measured."""
    measured = [r for r in report["unrouted"] if r["state"] != unrouted.UNMEASURED]
    assert [r["signature"] for r in measured] == ["placement_clause_failed"]


def test_a_capable_module_with_an_unmeasurable_archive_is_reported_as_such(report):
    """push_recover is a real policy with a recorded 2/5 -> 4/5 comparison, so graded_push
    HAS a capable module. Its recorded attempts were produced BY that policy, and replaying a
    policy over its own output cannot show what it changed. Three answers would be wrong:
    'no capable module' (one exists), 'already correct' (not measured), 'still wrong' (not
    measured either). It is a selection effect."""
    push = next(r for r in report["unrouted"] if r["signature"] == "graded_push")
    assert push["state"] == unrouted.UNMEASURED
    assert push["module_found"] is True
    assert push["candidate_consumers"] == ["executor_recovery"]


def test_the_selection_effect_is_named(report):
    push = next(r for r in report["unrouted"] if r["signature"] == "graded_push")
    assert "cannot measure" in push["why"] or "selection" in push["why"]
    assert push["probe"]["selection_effect"]


def test_the_policy_replay_is_correct(report):
    """The selection-effect note would be meaningless if the replay itself were broken."""
    push = next(r for r in report["unrouted"] if r["signature"] == "graded_push")
    probe = push["probe"]
    assert probe["verdicts_reproduced"] == len(probe["trials"]) > 0
    assert probe["attempts_replayed"] > 0


def test_a_selection_effect_is_not_scored_as_a_wrong_instance(report):
    """Counting it as instances_wrong would classify the signature FAILED_INSTANCES on no
    evidence, and produce a 'fix' for a defect nobody has shown exists."""
    push = next(r for r in report["unrouted"] if r["signature"] == "graded_push")
    assert push["probe"]["instances_wrong"] == 0
    assert push["probe"]["instances_checked"] == 0


def test_an_unprobed_signature_does_not_claim_a_verdict(report):
    """This test exists because the module's OWN first version failed it: it asserted
    "no capable module" for six signatures on the strength of their names, which is the
    unmeasured claim the module exists to prevent."""
    for row in report["unrouted"]:
        if row["state"] == unrouted.UNMEASURED and not row.get("module_found"):
            assert not row.get("probe")
            assert "no probe has been written" in row["why"]


def test_a_candidate_consumer_is_labelled_a_hypothesis(report):
    """A label is required exactly where a GUESS is offered. A signature whose module was
    actually found carries a probe, not a hypothesis, so demanding the label there would
    force a false one."""
    labelled = 0
    for row in report["unrouted"]:
        if row["state"] == unrouted.UNMEASURED and not row.get("module_found"):
            assert "NOT a measurement" in (row.get("probe_is") or "")
            labelled += 1
    assert labelled > 0


def test_the_claim_does_not_overstate_what_unrouted_means(report):
    assert "signature table" in report["claim"]
    assert "not about whether a module could act" in report["claim"]


def test_the_covered_failure_count_is_reported(report):
    """92 of 98 failures used to be dismissed with one sentence. The number has to be
    visible or the reader cannot tell how much was being waved past."""
    assert report["failures_covered"] > 0
    assert report["instances_covered"] > 0
