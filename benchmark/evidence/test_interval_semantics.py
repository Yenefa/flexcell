#!/usr/bin/env python3
"""A one-step contact is a measured interval, not an invalid one.

Run 43274720654 produced 15 contact intervals of which 2 had
start_sim_ns == end_sim_ns: the object was touching the pusher for exactly one
physics step. Schema v1 calls that "empty or inverted" and rejects the whole
bundle, so a contact that really happened made the run unevaluable - the
measurement was discarded for having an awkward shape.

The fix is versioned rather than a loosened check:

* v1 keeps its rule. Re-reading a historical bundle must not silently change the
  verdict it was graded under.
* v2 accepts a zero-length interval only when it declares single_frame: true and
  steps: 1, so no reader can mistake "one step" for "a duration that was
  measured".
* An inverted interval is still an error in both versions, and so is a
  single_frame flag on an interval that has a duration.

These tests are pure: no ROS, no simulator, no archived run required.
"""

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fixtures                                            # noqa: E402
import recorder                                            # noqa: E402
import schema                                              # noqa: E402


def bundle_v(version, intervals):
    """A valid bundle with the given interval list and schema version."""
    bundle = fixtures.base_bundle()
    bundle["schema_version"] = version
    bundle["contacts"]["intervals"] = intervals
    return bundle


SUSTAINED = {"start_sim_ns": 10_025_000_000, "end_sim_ns": 10_195_000_000,
             "other": "arm_link_6"}
SINGLE = {"start_sim_ns": 10_025_000_000, "end_sim_ns": 10_025_000_000,
          "other": "arm_link_6", "single_frame": True, "steps": 1}


def contacts_problems(bundle):
    return schema._problems_contacts(bundle["contacts"], bundle["schema_version"])


def test_the_untouched_fixture_is_valid():
    """The v1 fixture must stay valid: the new version may not retro-break it."""
    assert schema.validate(bundle_v(schema.SCHEMA_VERSION, [SUSTAINED])) == []


def test_sustained_interval_passes_in_v2():
    assert contacts_problems(bundle_v(schema.SCHEMA_VERSION_V2, [SUSTAINED])) == []


def test_single_frame_interval_passes_in_v2():
    problems = contacts_problems(bundle_v(schema.SCHEMA_VERSION_V2, [SINGLE]))
    assert problems == []


def test_mixed_intervals_pass_in_v2():
    problems = contacts_problems(bundle_v(schema.SCHEMA_VERSION_V2,
                                          [SINGLE, SUSTAINED, dict(SINGLE)]))
    assert problems == []


def test_v1_still_rejects_a_zero_length_interval():
    """History is read under the rule it was graded by, not under v2."""
    problems = contacts_problems(bundle_v(schema.SCHEMA_VERSION, [SINGLE]))
    assert any("empty or inverted interval" in p for p in problems)


def test_v2_rejects_a_zero_length_interval_that_does_not_declare_itself():
    undeclared = {"start_sim_ns": 10_025_000_000, "end_sim_ns": 10_025_000_000,
                  "other": "arm_link_6"}
    problems = contacts_problems(bundle_v(schema.SCHEMA_VERSION_V2, [undeclared]))
    assert any("must declare single_frame" in p for p in problems)


def test_v2_rejects_single_frame_with_inconsistent_step_count():
    wrong = dict(SINGLE, steps=3)
    problems = contacts_problems(bundle_v(schema.SCHEMA_VERSION_V2, [wrong]))
    assert any("must declare steps: 1" in p for p in problems)


def test_inverted_interval_is_still_rejected_in_v2():
    inverted = {"start_sim_ns": 10_195_000_000, "end_sim_ns": 10_025_000_000,
                "other": "arm_link_6"}
    problems = contacts_problems(bundle_v(schema.SCHEMA_VERSION_V2, [inverted]))
    assert any("inverted interval" in p for p in problems)


def test_single_frame_flag_on_a_real_interval_is_rejected():
    lying = dict(SUSTAINED, single_frame=True, steps=2)
    problems = contacts_problems(bundle_v(schema.SCHEMA_VERSION_V2, [lying]))
    assert any("single_frame is only valid" in p for p in problems)


def test_an_unknown_schema_version_is_rejected():
    problems = schema.validate(bundle_v("t08-evidence/9.9", [SUSTAINED]))
    assert any("schema_version" in p for p in problems)


def _contact_record(sim_ns, touching=True):
    contacts = {"contact": [{"collision1": {"name": "block-1::link"},
                             "collision2": {"name": "arm_link_6::collision"}}]} \
        if touching else {"contact": []}
    return {"sim_ns": sim_ns,
            "targets": {"block-1": {"component_present": True, "contacts": contacts}}}


def test_recorder_marks_a_one_step_contact_as_single_frame():
    intervals, present, _partners = recorder.contact_intervals(
        [_contact_record(10_025_000_000)], "block-1", ["arm_link_6::collision"])
    assert present is True
    assert len(intervals) == 1
    assert intervals[0]["steps"] == 1
    assert intervals[0]["single_frame"] is True
    assert intervals[0]["start_sim_ns"] == intervals[0]["end_sim_ns"]
    # And the produced shape is accepted by the schema version the recorder writes.
    assert schema.validate(bundle_v(schema.SCHEMA_VERSION_V2, intervals)) == []


def test_recorder_counts_a_multi_step_contact():
    records = [_contact_record(ns) for ns in (10_025_000_000, 10_030_000_000, 10_035_000_000)]
    intervals, _present, _partners = recorder.contact_intervals(
        records, "block-1", ["arm_link_6::collision"])
    assert len(intervals) == 1
    assert intervals[0]["steps"] == 3
    assert intervals[0]["single_frame"] is False
    assert intervals[0]["end_sim_ns"] > intervals[0]["start_sim_ns"]


def test_recorder_splits_a_gap_into_two_intervals():
    records = [_contact_record(10_025_000_000), _contact_record(10_030_000_000),
               _contact_record(10_035_000_000, touching=False),
               _contact_record(10_040_000_000)]
    intervals, _present, _partners = recorder.contact_intervals(
        records, "block-1", ["arm_link_6::collision"])
    assert [i["steps"] for i in intervals] == [2, 1]
    assert [i["single_frame"] for i in intervals] == [False, True]
