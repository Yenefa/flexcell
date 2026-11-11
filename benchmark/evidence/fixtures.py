#!/usr/bin/env python3
"""Deterministic synthetic evidence bundles for testing the verifier.

WHY SYNTHETIC BUNDLES AND NOT RECORDED RUNS
    Every gate must be provable in isolation. A recorded "good" run exercises
    all eight at once and tells you nothing when one fails; a fixture that
    differs from a valid bundle in exactly one field proves that gate alone is
    load-bearing.

The base bundle is a VALID pushed run: an object sliding on the table while a
pusher link touches it and the gripper stays open.
"""

import hashlib
import json
import math

SAMPLE_WIDTH = 10


def _quat_identity():
    return [0.0, 0.0, 0.0, 1.0]


def trajectory(start_sim_ns, count, rest_height, x0, dx, step_ns=5_000_000,
               role="target", lift=None, jump_at=None, skip_seq_at=None):
    """Build a strictly increasing sample list.

    lift: optional function(step_index) -> extra z, for lift-shaped traces.
    jump_at: optional (step_index, magnitude) applied to x at that step.
    skip_seq_at: optional index whose sequence number is skipped, simulating a
        dropped record.
    """
    samples = []
    sequence = 0
    sim = start_sim_ns
    for index in range(count):
        if skip_seq_at is not None and index == skip_seq_at:
            # Simulate a dropped record: the sequence skips a number while the
            # sim clock keeps moving, which is exactly what a lossy capture
            # looks like.
            sequence += 1
            sim += step_ns
        x = x0 + dx * index
        if jump_at is not None and index >= jump_at[0]:
            x += jump_at[1]
        z = rest_height + (lift(index) if lift else 0.0)
        samples.append([sequence, sim, 1_000_000_000 + sim, x, 0.0, z]
                       + _quat_identity())
        sequence += 1
        sim += step_ns
    return samples


def still_then_move(start_sim_ns, still_steps, move_steps, rest_height, dx):
    """A trace that is motionless for a while and then slides.

    Needed to test "contact happened, but not while the object was moving" -
    which cannot be built from an always-moving trace.
    """
    samples = []
    sequence = 0
    sim = start_sim_ns
    for index in range(still_steps + move_steps):
        x = 0.0 if index < still_steps else dx * (index - still_steps + 1)
        samples.append([sequence, sim, 1_000_000_000 + sim, x, 0.0, rest_height]
                       + _quat_identity())
        sequence += 1
        sim += 5_000_000
    return samples


def base_bundle(**overrides):
    """A valid bundle describing a genuine push.

    Overrides are applied by dotted path, e.g. "task.rest_height_m": 0.5.
    """
    rest = 0.25
    target = "block-1"
    protected = "block-2"

    # 40 steps of 5 ms: the target slides 200 mm in x while the pusher touches
    # it from step 5 to step 39.
    samples = trajectory(10_000_000_000, 40, rest, 0.0, 0.005)
    # The protected object never moves.
    still = trajectory(10_000_000_000, 40, rest, 5.0, 0.0, role="protected")

    # Gripper stays open the whole time: 0.06 rad, threshold will be 0.02.
    gripper_span = [[1_000_000_000 + 10_000_000 + 5_000_000 * i, 0.06]
                    for i in range(40)]

    bundle = {
        "schema_version": "t08-evidence/1.0",
        "task": {
            "task_id": "fixture",
            "task_sha256": hashlib.sha256(b"fixture").hexdigest(),
            "target_object": target,
            "protected_object": protected,
            "rest_height_m": rest,
        },
        "run": {
            "run_id": "fixture-run",
            "execution_window": {
                "start_sim_ns": 10_000_000_000,
                "end_sim_ns": 10_000_000_000 + 5_000_000 * 39,
                "start_mono_ns": 1_000_000_000,
                "end_mono_ns": 1_000_000_000 + 5_000_000 * 39,
            },
        },
        "source": {
            "trusted_source_id": "flexcell::PhysicsTrace/v1",
            "agent_reported": False,
        },
        "objects": {
            target: {
                "role": "target",
                "samples": samples,
                "sample_count": len(samples),
                "dropped_samples": 0,
                "max_gap_ns": 5_000_000,
            },
            protected: {
                "role": "protected",
                "samples": still,
                "sample_count": len(still),
                "dropped_samples": 0,
                "max_gap_ns": 5_000_000,
            },
        },
        "contacts": {
            "trusted_source_id": "flexcell::ContactTrace/v1",
            "pusher_links": ["arm_link_6"],
            "component_present": True,
            "intervals": [
                {
                    "start_sim_ns": 10_000_000_000 + 5_000_000 * 5,
                    "end_sim_ns": 10_000_000_000 + 5_000_000 * 39,
                    "other": "arm_link_6",
                }
            ],
        },
        "gripper": {
            "joint_name": "gripper_finger_joint",
            "min_aperture_rad": 0.0,
            "max_aperture_rad": 0.08,
            "span": gripper_span,
        },
        "attachment": {"events": 0, "attached_during_window": False},
        "teleport": {
            "max_single_step_jump_m": 0.005,
            "jump_threshold_m": 0.030,
        },
        "manifest": {},
    }
    bundle["manifest"] = {
        "files": {"physics.jsonl": hashlib.sha256(b"physics").hexdigest()},
    }
    for path, value in overrides.items():
        _set(bundle, path, value)
    # The digest is computed last so it always matches the final content.
    from schema import bundle_sha256
    bundle["manifest"]["bundle_sha256"] = bundle_sha256(bundle)
    return bundle


def _set(bundle, path, value):
    keys = path.split(".")
    node = bundle
    for key in keys[:-1]:
        node = node[key]
    node[keys[-1]] = value


def terminal_verdict(passed=True):
    return {
        "evaluator_version": "0.4.0",
        "passed": passed,
        "failed_clauses": [] if passed else ["displacement"],
    }


def limits():
    """The limits T08 actually declares.

    Using the real 5 mm lift and a calibrated non-grasping aperture matters:
    a generous invented limit would let the negative tests pass for reasons the
    real task would not accept.
    """
    return {"max_lift_during_m": 0.005,
            # Fingers may wobble a fraction of a millimetre; closing on an
            # object is centimetres. 2 mm separates the two cleanly.
            "max_aperture_change_rad": 0.002,
            "protected_move_m": 0.005}
