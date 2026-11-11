#!/usr/bin/env python3
"""The eight mandatory negatives, plus the mutation suite.

WHY EACH NEGATIVE ASSERTS ON A NAMED GATE
    Asserting only "passed is False" would let a broken fixture pass for the
    wrong reason - a bundle that fails schema validation also returns
    passed=False, and would happily stand in for "lift detected". Each test
    therefore also asserts WHICH gate rejected it, so the eight cases cannot
    collapse into one another.

WHY THE MUTATIONS EXIST
    A gate is only load-bearing if removing its evidence breaks the verdict.
    Each mutation deletes exactly one required channel and requires the
    verifier to reject; a verifier that still passed would be reporting a
    judgement it had no evidence for.
"""

import copy
import math
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fixtures                                          # noqa: E402
import schema                                            # noqa: E402
import verify                                            # noqa: E402


def judge(bundle, terminal=None, limits=None):
    return verify.verify(
        bundle,
        fixtures.terminal_verdict(True) if terminal is None else terminal,
        fixtures.limits() if limits is None else limits)


def assert_rejected(result, gate):
    assert result["passed"] is False, "verifier passed a bundle it should reject"
    assert gate in result["failed_gates"], (
        "rejected for the wrong reason: expected gate %r, failed %r"
        % (gate, result["failed_gates"]))
    assert result["failure_reason"], "a rejection must carry a reason"


# --------------------------------------------------------------- 1. positive
def test_1_a_valid_push_passes():
    result = judge(fixtures.base_bundle())
    assert result["passed"] is True, result["failure_reason"]
    assert result["physical_outcome"] == "PUSHED"
    assert result["evidence_status"] == "COMPLETE"


# ------------------------------------------------ 2. lift, carry, return down
def test_2_lift_carry_and_return_to_original_height_fails():
    """The mis-grade that end-state grading cannot see.

    The object ends at rest height, so a terminal-only evaluator passes. It was
    carried 60 mm up and back down, and max_z is the only place that shows.
    """
    bundle = fixtures.base_bundle()
    target = bundle["task"]["target_object"]
    rest = bundle["task"]["rest_height_m"]
    # Lift to +60 mm in the middle, then back to rest: first and last z match.
    bundle["objects"][target]["samples"] = fixtures.trajectory(
        10_000_000_000, 40, rest, 0.0, 0.005,
        lift=lambda i: 0.060 * math.sin(math.pi * i / 39.0))
    result = judge(bundle)
    assert_rejected(result, "no_lift")
    gate = next(g for g in result["gates"] if g["gate"] == "no_lift")
    assert gate["evidence"]["max_lift_m"] > fixtures.limits()["max_lift_during_m"]


def test_2b_a_lift_inside_the_allowed_band_is_still_allowed():
    """Control: the gate must not reject every motion in z.

    A real push rides at rest height +- a millimetre. If the lift limit were
    effectively zero the suite would pass by rejecting everything, which is the
    degenerate verifier this whole file is trying to avoid.
    """
    bundle = fixtures.base_bundle()
    target = bundle["task"]["target_object"]
    rest = bundle["task"]["rest_height_m"]
    bundle["objects"][target]["samples"] = fixtures.trajectory(
        10_000_000_000, 40, rest, 0.0, 0.005,
        lift=lambda i: 0.001)
    result = judge(bundle)
    assert result["passed"] is True, result["failure_reason"]


# ------------------------------------------- 3. carry at roughly constant height
def test_3_carry_at_constant_height_fails():
    """Moving without touching the table is not pushing, whatever z says.

    The object is carried at a constant height, so max_z never spikes and the
    lift gate alone would pass. What exposes it is that it was never supported
    by the table and the gripper was closed.
    """
    bundle = fixtures.base_bundle()
    target = bundle["task"]["target_object"]
    rest = bundle["task"]["rest_height_m"]
    # Held 50 mm above the table the entire time, perfectly level.
    bundle["objects"][target]["samples"] = fixtures.trajectory(
        10_000_000_000, 40, rest + 0.050, 0.0, 0.005)
    result = judge(bundle)
    assert_rejected(result, "table_support")


def test_3b_a_constant_height_carry_also_trips_the_lift_gate():
    """Two independent gates should agree, not merely one.

    Belt and braces is the point: if only one gate caught a carry, a
    regression in that gate would silently reopen the hole.
    """
    bundle = fixtures.base_bundle()
    target = bundle["task"]["target_object"]
    rest = bundle["task"]["rest_height_m"]
    bundle["objects"][target]["samples"] = fixtures.trajectory(
        10_000_000_000, 40, rest + 0.050, 0.0, 0.005)
    result = judge(bundle)
    assert "no_lift" in result["failed_gates"]
    assert "table_support" in result["failed_gates"]


# --------------------------------------------------- 4. lift 25 mm and place back
def test_3c_disturbing_the_protected_object_fails():
    """T08 forbids moving the blue block; that must be a gate, not a hope.

    Found by the signature test: before this gate existed, dragging the
    protected object passed all eight others.
    """
    bundle = fixtures.base_bundle()
    protected = bundle["task"]["protected_object"]
    bundle["objects"][protected]["samples"] = fixtures.trajectory(
        10_000_000_000, 40, bundle["task"]["rest_height_m"], 5.0, 0.005)
    result = judge(bundle)
    assert_rejected(result, "protected_unmoved")


def test_3d_a_protected_object_nudged_and_returned_still_fails():
    """Ending where it started does not mean it was never disturbed."""
    bundle = fixtures.base_bundle()
    protected = bundle["task"]["protected_object"]
    samples = fixtures.trajectory(
        10_000_000_000, 40, bundle["task"]["rest_height_m"], 5.0, 0.0)
    for index in range(10, 20):
        samples[index][3] += 0.020          # pushed 20 mm and back
    bundle["objects"][protected]["samples"] = samples
    result = judge(bundle)
    assert_rejected(result, "protected_unmoved")


def test_4_lift_25mm_and_place_back_fails():
    """A small lift that still exceeds the allowed band."""
    bundle = fixtures.base_bundle()
    target = bundle["task"]["target_object"]
    rest = bundle["task"]["rest_height_m"]
    samples = fixtures.trajectory(10_000_000_000, 40, rest, 0.0, 0.005,
                                  lift=lambda i: 0.025 if i >= 10 else 0.0)
    bundle["objects"][target]["samples"] = samples
    result = judge(bundle)
    assert_rejected(result, "no_lift")
    gate = next(g for g in result["gates"] if g["gate"] == "no_lift")
    assert gate["evidence"]["max_lift_m"] == pytest.approx(0.025, abs=1e-6)


# ------------------------------- 5. object moves with no pusher contact
def test_5_motion_without_pusher_contact_fails():
    """The object slid but the pusher never touched it.

    This is the gate that distinguishes "contact was measured" from "the arm
    was nearby and the object moved, so presumably it pushed".
    """
    bundle = fixtures.base_bundle()
    bundle["contacts"]["intervals"] = []
    result = judge(bundle)
    assert_rejected(result, "pusher_contact")


def test_5b_contact_from_a_body_that_is_not_the_pusher_fails():
    """Contact with the floor or another object is not a push."""
    bundle = fixtures.base_bundle()
    bundle["contacts"]["intervals"] = [{
        "start_sim_ns": 10_000_000_050,
        "end_sim_ns": 10_000_000_200,
        "other": "ground_plane/link/collision",
    }]
    result = judge(bundle)
    assert_rejected(result, "pusher_contact")


def test_5c_contact_that_never_overlaps_the_motion_fails():
    """Touching before the object moved proves nothing about the motion.

    The trace is still for 20 steps and then slides, and the only contact sits
    inside the still period. A gate that merely asked "was there any contact"
    would pass this; the overlap rule is what rejects it.
    """
    bundle = fixtures.base_bundle()
    target = bundle["task"]["target_object"]
    rest = bundle["task"]["rest_height_m"]
    samples = fixtures.still_then_move(10_000_000_000, 20, 20, rest, 0.005)
    bundle["objects"][target]["samples"] = samples
    bundle["objects"][target]["sample_count"] = len(samples)
    # Contact only during the motionless period.
    bundle["contacts"]["intervals"] = [{
        "start_sim_ns": 10_000_000_000,
        "end_sim_ns": 10_000_000_000 + 5_000_000 * 10,
        "other": "arm_link_6",
    }]
    result = judge(bundle)
    assert_rejected(result, "pusher_contact")
    gate = next(g for g in result["gates"] if g["gate"] == "pusher_contact")
    assert gate["evidence"]["motion_windows"] > 0


# ------------------------------------------------ 6. missing trajectory
def test_6_missing_trajectory_fails():
    bundle = fixtures.base_bundle()
    del bundle["objects"]
    result = judge(bundle)
    assert_rejected(result, "trajectory")
    assert result["physical_outcome"] == "UNKNOWN"
    assert "INCOMPLETE" in result["evidence_status"]


def test_6b_an_empty_trajectory_is_not_a_clean_one():
    bundle = fixtures.base_bundle()
    target = bundle["task"]["target_object"]
    bundle["objects"][target]["samples"] = []
    bundle["objects"][target]["sample_count"] = 0
    result = judge(bundle)
    assert_rejected(result, "trajectory")


def test_6c_missing_the_protected_object_fails():
    """Absence of evidence about the protected object is not evidence of safety.

    T08 forbids moving the blue block. A trajectory that never looks at it
    cannot show it stayed put.
    """
    bundle = fixtures.base_bundle()
    del bundle["objects"][bundle["task"]["protected_object"]]
    result = judge(bundle)
    assert_rejected(result, "trajectory")


# --------------------------- 7. truncated / discontinuous trajectory
def test_7_a_skipped_sequence_number_fails():
    """A dropped record is a gap in the evidence, not a shorter trajectory."""
    bundle = fixtures.base_bundle()
    target = bundle["task"]["target_object"]
    samples = fixtures.trajectory(10_000_000_000, 40, 0.25, 0.0, 0.005,
                                  skip_seq_at=17)
    bundle["objects"][target]["samples"] = samples
    bundle["objects"][target]["sample_count"] = len(samples)
    result = judge(bundle)
    assert_rejected(result, "trajectory")


def test_7b_a_sample_gap_larger_than_declared_fails():
    bundle = fixtures.base_bundle()
    target = bundle["task"]["target_object"]
    samples = fixtures.trajectory(10_000_000_000, 40, 0.25, 0.0, 0.005)
    # Insert a 100 ms hole at index 20 without breaking the sequence numbers.
    for index in range(20, len(samples)):
        samples[index][1] += 100_000_000
        samples[index][2] += 100_000_000
    bundle["objects"][target]["samples"] = samples
    result = judge(bundle)
    assert_rejected(result, "trajectory")


def test_7c_a_non_finite_value_fails():
    """NaN in a pose is a corrupt read, never a valid measurement."""
    bundle = fixtures.base_bundle()
    target = bundle["task"]["target_object"]
    bundle["objects"][target]["samples"][5][3] = float("nan")
    result = judge(bundle)
    assert_rejected(result, "trajectory")


def test_7d_a_non_unit_quaternion_fails():
    bundle = fixtures.base_bundle()
    target = bundle["task"]["target_object"]
    bundle["objects"][target]["samples"][5][6:10] = [0.0, 0.0, 0.0, 0.0]
    result = judge(bundle)
    assert_rejected(result, "trajectory")


def test_7e_a_declared_count_that_disagrees_with_the_data_fails():
    bundle = fixtures.base_bundle()
    target = bundle["task"]["target_object"]
    bundle["objects"][target]["sample_count"] += 1
    result = judge(bundle)
    assert_rejected(result, "trajectory")


# ------------------------------------------------- 8. direct model teleport
def test_8_a_direct_teleport_fails():
    """The object jumped between two physics steps.

    Nothing in the contact or lift channels sees this: the object arrives at
    rest height having been touched by nobody. The single-step jump is the only
    signature, which is why it gets its own gate.
    """
    bundle = fixtures.base_bundle()
    target = bundle["task"]["target_object"]
    bundle["objects"][target]["samples"] = fixtures.trajectory(
        10_000_000_000, 40, 0.25, 0.0, 0.0, jump_at=(20, 0.080))
    result = judge(bundle)
    assert_rejected(result, "no_teleport")


def test_8d_a_declaration_that_contradicts_its_own_samples_fails():
    """If declared and measured jump disagree, the record is not reliable.

    This is the case a "trust the bundle" verifier would miss: the samples show
    a clean push, but the bundle claims a jump it did not record (or vice
    versa). Either way the two cannot both be true.
    """
    bundle = fixtures.base_bundle()
    bundle["teleport"]["max_single_step_jump_m"] = 0.0001   # claims near-zero
    result = judge(bundle)
    gate = next(g for g in result["gates"] if g["gate"] == "no_teleport")
    assert gate["ok"] is False
    assert "disagrees" in (gate["reason"] or "")


def test_8b_a_teleport_measured_as_unmeasured_fails_closed():
    """Not checking for a teleport is not the same as ruling one out."""
    bundle = fixtures.base_bundle()
    bundle["teleport"]["max_single_step_jump_m"] = None
    result = judge(bundle)
    assert_rejected(result, "no_teleport")


def test_8c_a_run_cannot_widen_its_own_teleport_threshold():
    """Declaring a 500 mm threshold must not make an 80 mm jump acceptable.

    The threshold is part of the evidence, so a run could otherwise admit any
    jump by declaring a large enough limit. The verifier caps it at its own
    physical bound.
    """
    bundle = fixtures.base_bundle()
    target = bundle["task"]["target_object"]
    bundle["objects"][target]["samples"] = fixtures.trajectory(
        10_000_000_000, 40, 0.25, 0.0, 0.0, jump_at=(20, 0.080))
    bundle["teleport"]["max_single_step_jump_m"] = 0.080
    bundle["teleport"]["jump_threshold_m"] = 0.500
    result = judge(bundle)
    assert_rejected(result, "no_teleport")
    gate = next(g for g in result["gates"] if g["gate"] == "no_teleport")
    assert gate["evidence"]["threshold_m"] <= verify.TELEPORT_JUMP_M


# -------------------------------------------------- attachment and gripper
def test_an_attachment_event_fails():
    bundle = fixtures.base_bundle()
    bundle["attachment"]["attached_during_window"] = True
    bundle["attachment"]["events"] = 1
    result = judge(bundle)
    assert_rejected(result, "no_attachment")


def test_a_close_carry_reopen_gripper_fails():
    """A grasp is aperture MOTION, and the whole span is what shows it.

    The gripper closes on the object, carries it, and reopens. No single reading
    looks wrong; only the span does.
    """
    bundle = fixtures.base_bundle()
    span = bundle["gripper"]["span"]
    for index in range(10, 30):
        span[index] = [span[index][0], 0.010]   # fingers close by 50 mm
    result = judge(bundle)
    assert_rejected(result, "gripper")


def test_a_push_with_closed_fingers_is_accepted():
    """Falsified by real telemetry: this robot pushes with the fingers CLOSED.

    A real push measured aperture ~0.000 rad across all 937 joint samples. A
    gate that demanded an OPEN gripper rejected every genuine push, which is the
    same defect as one that accepts everything, mirrored.
    """
    bundle = fixtures.base_bundle()
    bundle["gripper"]["span"] = [[t, 0.0] for t, _v in bundle["gripper"]["span"]]
    result = judge(bundle)
    assert result["passed"] is True, result["failure_reason"]


def test_a_stable_open_gripper_is_also_accepted():
    """Constant aperture is what matters, not its absolute value."""
    bundle = fixtures.base_bundle()
    result = judge(bundle)
    assert result["passed"] is True, result["failure_reason"]


def test_a_missing_gripper_span_fails():
    bundle = fixtures.base_bundle()
    bundle["gripper"]["span"] = []
    result = judge(bundle)
    assert_rejected(result, "gripper")


# ------------------------------------------------------- terminal must pass
def test_a_failed_terminal_verdict_cannot_be_rescued_by_physics():
    """A clean push still fails T08 if the terminal clauses say so.

    The 30 mm gate is the task's, not the verifier's. This layer may not
    overrule it - which is the whole reason the two are separate versions.
    """
    result = judge(fixtures.base_bundle(),
                   terminal=fixtures.terminal_verdict(False))
    assert_rejected(result, "terminal")
    assert result["physical_outcome"] == "UNKNOWN"


def test_no_terminal_verdict_at_all_fails_closed():
    result = verify.verify(fixtures.base_bundle(), None, fixtures.limits())
    assert_rejected(result, "terminal")


# ------------------------------------------------------------- the mutations
MUTATIONS = [
    ("drop the trajectory", lambda b: b.pop("objects")),
    ("drop the protected object",
     lambda b: b["objects"].pop(b["task"]["protected_object"])),
    ("drop the contact intervals", lambda b: b["contacts"].update(intervals=[])),
    ("drop the pusher link identity",
     lambda b: b["contacts"].update(pusher_links=[])),
    ("claim the contact component was absent",
     lambda b: b["contacts"].update(component_present=False)),
    ("drop the gripper span", lambda b: b["gripper"].update(span=[])),
    ("drop the teleport measurement",
     lambda b: b["teleport"].update(max_single_step_jump_m=None)),
    ("drop the attachment count", lambda b: b["attachment"].pop("events")),
    ("mark the evidence as agent-reported",
     lambda b: b["source"].update(agent_reported=True)),
    ("point at an untrusted source",
     lambda b: b["source"].update(trusted_source_id="skill_report")),
    ("drop the manifest", lambda b: b.pop("manifest")),
    ("drop the task identity", lambda b: b["task"].pop("task_sha256")),
]


@pytest.mark.parametrize("label,mutate", MUTATIONS,
                         ids=[m[0] for m in MUTATIONS])
def test_removing_a_required_channel_makes_the_verifier_reject(label, mutate):
    bundle = fixtures.base_bundle()
    mutate(bundle)
    result = judge(bundle)
    assert result["passed"] is False, (
        "%r did not change the verdict: the verifier accepted a bundle with a "
        "required evidence channel removed" % label)
    assert result["failure_reason"], "rejection must be explained"


def test_the_mutation_baseline_is_actually_valid():
    """Control: without a valid baseline the mutation test proves nothing."""
    assert judge(fixtures.base_bundle())["passed"] is True


def test_well_formed_but_wrong_bundles_fail_through_different_gates():
    """If every physical violation failed the same way, one gate would be doing
    all the work and the rest would be decoration.

    Only PHYSICS-level violations are compared here. Deleting a channel makes
    the bundle malformed, and a malformed bundle legitimately fails everything
    at once - mixing the two would compare "corrupt" with "carried" and learn
    nothing.
    """
    physics = {
        "carried at constant height": lambda b: b["objects"][
            b["task"]["target_object"]].update(samples=fixtures.trajectory(
                10_000_000_000, 40, b["task"]["rest_height_m"] + 0.050, 0.0,
                0.005)),
        "attachment present": lambda b: b["attachment"].update(
            attached_during_window=True, events=1),
        "gripper closed mid-run": lambda b: b["gripper"]["span"].__setitem__(
            20, [b["gripper"]["span"][20][0], 0.001]),
        "teleport jump": lambda b: b["objects"][
            b["task"]["target_object"]].update(samples=fixtures.trajectory(
                10_000_000_000, 40, b["task"]["rest_height_m"], 0.0, 0.0,
                jump_at=(20, 0.080))),
        "protected object dragged": lambda b: b["objects"][
            b["task"]["protected_object"]].update(samples=fixtures.trajectory(
                10_000_000_000, 40, b["task"]["rest_height_m"], 5.0, 0.005)),
        "no motion at all": lambda b: b["objects"][
            b["task"]["target_object"]].update(samples=fixtures.trajectory(
                10_000_000_000, 40, b["task"]["rest_height_m"], 0.0, 0.0)),
    }
    signatures = {}
    for label, mutate in physics.items():
        bundle = fixtures.base_bundle()
        mutate(bundle)
        result = judge(bundle)
        assert result["passed"] is False, "%r was accepted" % label
        signatures[label] = tuple(result["failed_gates"])
    distinct = {v for v in signatures.values()}
    assert len(distinct) >= 4, (
        "physics violations collapse onto too few gate signatures: %r"
        % (signatures,))


# ------------------------------------------------------------ the three fields
def test_a_contradicted_push_is_not_reported_as_unknown():
    """Evidence readable and contradicting the push is NOT a measurement gap."""
    bundle = fixtures.base_bundle()
    bundle["attachment"]["attached_during_window"] = True
    result = judge(bundle)
    assert result["physical_outcome"] == "NOT_PUSHED"
    assert result["evidence_status"] == "COMPLETE_EVIDENCE_CONTRADICTS_PUSH"


def test_an_invalid_bundle_reports_unknown_not_failure():
    """Missing telemetry is a measurement problem, not a robot failure.

    Conflating these is how a broken sensor becomes a reported robot failure,
    and it is the specific mistake the three-field output exists to prevent.
    """
    bundle = fixtures.base_bundle()
    bundle.pop("objects")
    result = judge(bundle)
    assert result["physical_outcome"] == "UNKNOWN"
    assert "INCOMPLETE" in result["evidence_status"]
    assert result["failure_reason"]


def test_every_gate_appears_exactly_once_in_the_output():
    bundle = fixtures.base_bundle()
    bundle.pop("objects")
    result = judge(bundle)
    names = [g["gate"] for g in result["gates"]]
    assert len(names) == len(set(names)) == 9
    assert set(names) == {"terminal", "trajectory", "table_support",
                          "protected_unmoved", "no_lift", "pusher_contact",
                          "gripper", "no_attachment", "no_teleport"}
