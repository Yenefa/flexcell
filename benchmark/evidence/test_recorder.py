#!/usr/bin/env python3
"""Recorder tests against REAL recorded step logs, not invented JSON.

WHY REAL LOGS
    The recorder's whole job is to read what the Gazebo plugins actually write.
    A fixture written from the same mental model as the reader would agree with
    the reader and prove nothing. The log used here was produced by the real
    ContactTrace plugin in an earlier contact qualification run, so its field
    names, nesting and value types are the ones the recorder must survive.

WHY THE DEGRADED CASES MATTER
    Every failure the recorder can see is a failure the verifier must inherit.
    If the recorder silently repaired a gap, the verifier would receive a clean
    bundle and pass a run whose evidence had holes.
"""

import json
import math
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import recorder                                           # noqa: E402
import schema                                             # noqa: E402
import verify                                             # noqa: E402
import fixtures                                           # noqa: E402

REPO = Path('/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell')
REAL_CONTACT_LOG = (REPO / 'code-clone' / 'artifacts' / 'native-stale-20261031' /
                    'ci-base' / 'native-five-window' / 'contact_steps.jsonl')

needs_real_log = pytest.mark.skipif(
    not REAL_CONTACT_LOG.is_file(),
    reason='archived contact step log not present')


def write_jsonl(path, records):
    path.write_text('\n'.join(json.dumps(r) for r in records) + '\n',
                    encoding='utf-8')
    return str(path)


def physics_records(count=10, model='block-1', x_step=0.005, rest=0.25,
                    lift=None, joint=False):
    records = []
    for index in range(count):
        records.append({
            'schema_version': 1,
            'sim_ns': 10_000_000_000 + 5_000_000 * index,
            'step_ns': 5_000_000,
            'monotonic_ns': 1_000_000_000 + 5_000_000 * index,
            'parent_pose': [0, 0, 0.1, 0, 0, 0, 1],
            'objects': {
                model: {
                    'pose': [x_step * index, 0.0,
                             rest + (lift(index) if lift else 0.0),
                             0.0, 0.0, 0.0, 1.0],
                    'joint_component': joint,
                },
                'block-2': {'pose': [5.0, 0.0, rest, 0.0, 0.0, 0.0, 1.0],
                            'joint_component': False},
            },
        })
    return records


# ------------------------------------------------ reading the real plugin log
@needs_real_log
def test_the_real_contact_log_parses_and_yields_intervals():
    """A real ContactTrace log must be readable by the recorder unchanged."""
    records = recorder._read_jsonl(str(REAL_CONTACT_LOG))
    assert len(records) > 1000
    first = records[0]
    assert 'sim_ns' in first and 'targets' in first
    intervals, present, partners = recorder.contact_intervals(
        records, 'target_box_a', ['ground_plane::link::collision'])
    assert present is True, 'the real log must show the contact component present'
    assert intervals, 'the real log must contain at least one contact interval'
    assert 'ground_plane::link::collision' in partners
    # Intervals must be ordered and non-empty.
    for interval in intervals:
        assert interval['end_sim_ns'] >= interval['start_sim_ns']


@needs_real_log
def test_the_real_contact_log_records_the_floor_as_a_partner():
    """The box rests on the floor; that contact must be visible and named.

    This is what lets the verifier refuse "contact with anything" as proof of a
    push: the floor is a partner on almost every step, and a gate that accepted
    any contact would pass a run where nothing ever touched the box.
    """
    records = recorder._read_jsonl(str(REAL_CONTACT_LOG))
    _intervals, _present, partners = recorder.contact_intervals(
        records, 'target_box_a', [])
    assert any('ground_plane' in p for p in partners)


# ----------------------------------------------------------- trajectory shape
def test_a_clean_trajectory_has_no_dropped_samples(tmp_path):
    path = write_jsonl(tmp_path / 'physics.jsonl', physics_records())
    samples, dropped, gap = recorder.trajectory_from_physics(
        recorder._read_jsonl(path), 'block-1')
    assert len(samples) == 10
    assert dropped == 0
    assert gap == 5_000_000
    assert all(len(s) == 10 for s in samples)


def test_a_missing_object_is_counted_as_dropped_not_skipped(tmp_path):
    """An absent model is a gap in the evidence, and must be counted as one."""
    records = physics_records()
    for index in (3, 4):
        del records[index]['objects']['block-1']
    path = write_jsonl(tmp_path / 'physics.jsonl', records)
    samples, dropped, _gap = recorder.trajectory_from_physics(
        recorder._read_jsonl(path), 'block-1')
    assert dropped == 2
    assert len(samples) == 8


def test_a_non_finite_pose_is_dropped_not_recorded(tmp_path):
    records = physics_records()
    records[2]['objects']['block-1']['pose'][2] = float('nan')
    path = write_jsonl(tmp_path / 'physics.jsonl', records)
    samples, dropped, _gap = recorder.trajectory_from_physics(
        recorder._read_jsonl(path), 'block-1')
    assert dropped == 1
    assert all(math.isfinite(s[5]) for s in samples)


def test_sequence_numbers_are_strictly_increasing(tmp_path):
    path = write_jsonl(tmp_path / 'physics.jsonl', physics_records())
    samples, _d, _g = recorder.trajectory_from_physics(
        recorder._read_jsonl(path), 'block-1')
    sequences = [s[0] for s in samples]
    assert sequences == sorted(set(sequences))


# -------------------------------------------------------------- contact edges
def test_contact_intervals_are_split_when_contact_breaks():
    records = []
    for index in range(10):
        touching = index in (1, 2, 3, 7, 8)
        contact = {'contact': [{
            'collision1': {'name': 'block-1::link::col'},
            'collision2': {'name': 'arm::link6::col'},
        }]} if touching else {'contact': []}
        records.append({'sim_ns': 1000 * index,
                        'targets': {'block-1': {'component_present': True,
                                                'contacts': contact}}})
    intervals, present, _p = recorder.contact_intervals(
        records, 'block-1', ['arm::link6::col'])
    assert present is True
    assert len(intervals) == 2, intervals
    assert intervals[0]['start_sim_ns'] == 1000
    assert intervals[1]['start_sim_ns'] == 7000


def test_an_absent_contact_component_is_reported_as_absent():
    """Silence on the contact topic is not an empty contact set."""
    records = [{'sim_ns': 1000 * index,
                'targets': {'block-1': {'component_present': False,
                                        'contacts': None}}}
               for index in range(5)]
    _intervals, present, _partners = recorder.contact_intervals(
        records, 'block-1', ['arm::link6::col'])
    assert present is False


# ------------------------------------------------------------ end-to-end build
def _build(tmp_path, physics=None, contact=None, joints=None, **over):
    task = tmp_path / 'task.json'
    task.write_text(json.dumps({'task_id': 'fixture'}), encoding='utf-8')
    args = dict(
        physics_log=write_jsonl(tmp_path / 'physics.jsonl',
                                physics if physics is not None else physics_records()),
        contact_log=(write_jsonl(tmp_path / 'contact.jsonl', contact)
                     if contact is not None else None),
        joint_log=(write_jsonl(tmp_path / 'joints.jsonl', joints)
                   if joints is not None else None),
        task=str(task), task_id='fixture', run_id='r1',
        target='block-1', protected='block-2', rest_height=0.25,
        pusher_links=['arm::link6::col'], gripper_joint='gripper_finger_joint')
    args.update(over)
    namespace = type('Args', (), args)()
    return recorder.build(namespace)


def _contact_records(count=10, touching_from=2):
    return [{
        'sim_ns': 10_000_000_000 + 5_000_000 * index,
        'targets': {'block-1': {
            'component_present': True,
            'contacts': {'contact': [{
                'collision1': {'name': 'block-1::link::col'},
                'collision2': {'name': 'arm::link6::col'},
            }]} if index >= touching_from else {'contact': []}}},
    } for index in range(count)]


def _joint_records(count=10, aperture=0.06):
    return [{'monotonic_ns': 1_000_000_000 + 5_000_000 * i,
             'name': ['gripper_finger_joint', 'joint1'],
             'position': [aperture, 0.0]} for i in range(count)]


def test_a_complete_bundle_passes_schema_validation(tmp_path):
    bundle = _build(tmp_path, contact=_contact_records(),
                    joints=_joint_records())
    problems = schema.validate(bundle)
    assert problems == [], problems


def test_a_bundle_without_contact_logs_is_refused_by_the_schema(tmp_path):
    """No contact log is not an empty contact set.

    The recorder must not manufacture component_present=True from silence: that
    flag is the only thing distinguishing "nothing touched it" from "we were not
    looking", and the schema refuses to accept a bundle that cannot tell.
    """
    bundle = _build(tmp_path)
    problems = schema.validate(bundle)
    assert any('component_present' in p for p in problems), problems


def test_the_bundle_declares_an_untrusted_agent_flag_false(tmp_path):
    bundle = _build(tmp_path, contact=_contact_records())
    assert bundle['source']['agent_reported'] is False
    assert bundle['source']['trusted_source_id'] in schema.TRUSTED_SOURCES


def test_the_bundle_records_the_task_digest(tmp_path):
    bundle = _build(tmp_path, contact=_contact_records())
    assert len(bundle['task']['task_sha256']) == 64


def test_the_manifest_covers_every_input_file(tmp_path):
    bundle = _build(tmp_path, contact=_contact_records())
    assert 'physics.jsonl' in bundle['manifest']['files']
    assert len(bundle['manifest']['bundle_sha256']) == 64


def test_a_joint_component_anywhere_is_recorded_as_an_attachment(tmp_path):
    """PhysicsTrace's joint_component is the stack's real carry mechanism."""
    bundle = _build(tmp_path, physics=physics_records(joint=True),
                    contact=_contact_records())
    assert bundle['attachment']['attached_during_window'] is True
    assert bundle['attachment']['events'] > 0


def test_the_bundle_carries_the_measured_jump_not_an_assumed_one(tmp_path):
    records = physics_records()
    for index in range(5, 10):
        records[index]['objects']['block-1']['pose'][0] += 0.080
    bundle = _build(tmp_path, physics=records, contact=_contact_records())
    assert bundle['teleport']['max_single_step_jump_m'] >= 0.079


def test_an_empty_physics_log_is_refused(tmp_path):
    with pytest.raises(SystemExit):
        _build(tmp_path, physics=[])


# ----------------------------------------- recorder output drives the verifier
def test_a_recorded_clean_push_passes_the_verifier(tmp_path):
    """End to end: plugin-log shape -> recorder -> verifier -> PASS."""
    bundle = _build(tmp_path, contact=_contact_records(),
                    joints=_joint_records())
    result = verify.verify(bundle, fixtures.terminal_verdict(True),
                           fixtures.limits())
    assert result["passed"] is True, result["failure_reason"]


def test_a_recorded_run_without_contact_logs_fails_the_verifier(tmp_path):
    """No contact evidence must not be read as "no contact occurred"."""
    bundle = _build(tmp_path)
    result = verify.verify(bundle, fixtures.terminal_verdict(True),
                           fixtures.limits())
    assert result["passed"] is False
    assert "pusher_contact" in result["failed_gates"]
