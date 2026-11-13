"""Issue #239: contact intervals must represent single-frame, sustained and mixed contact."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import recorder
import schema

STEP = 5_000_000
PUSHER = 'open_manipulator_x::gripper_left_link::gripper_left_link_collision'
BOX = 'target_box_a::link::col'


def _record(sim_ns, touching):
    contacts = []
    if touching:
        contacts.append({'collision1': {'name': BOX},
                         'collision2': {'name': PUSHER}})
    return {
        'sim_ns': sim_ns,
        'step_ns': STEP,
        'targets': {'target_box_a': {
            'component_present': True,
            'contacts': {'contact': contacts},
        }},
    }


def _check_schema(intervals):
    section = {
        'trusted_source_id': 'flexcell::PhysicsTrace/v1',
        'pusher_links': [PUSHER],
        'component_present': True,
        'interval_representation': recorder.CONTACT_INTERVAL_REPRESENTATION,
        'intervals': intervals,
    }
    problems = schema._problems_contacts(section)
    return [p for p in problems if 'interval' in p]


def test_single_frame_contact_has_a_real_nonzero_span():
    """The CI_L0 defect: one step of contact used to produce start == end."""
    records = [_record(0, False), _record(STEP, True), _record(2 * STEP, False)]
    intervals, present, _ = recorder.contact_intervals(records, 'target_box_a', [PUSHER])
    assert len(intervals) == 1
    iv = intervals[0]
    assert iv['start_sim_ns'] == STEP
    assert iv['end_sim_ns'] == 2 * STEP
    assert iv['end_sim_ns'] - iv['start_sim_ns'] == STEP  # exactly one real physics step
    assert _check_schema(intervals) == []


def test_sustained_contact_spans_every_step():
    records = [_record(i * STEP, True) for i in range(4)] + [_record(4 * STEP, False)]
    intervals, _, _ = recorder.contact_intervals(records, 'target_box_a', [PUSHER])
    assert len(intervals) == 1
    iv = intervals[0]
    assert iv['start_sim_ns'] == 0
    # four contact steps, so the half-open span is 4 * STEP, not 3 * STEP
    assert iv['end_sim_ns'] - iv['start_sim_ns'] == 4 * STEP
    assert _check_schema(intervals) == []


def test_mixed_single_and_sustained_are_both_kept():
    """No event may be dropped to make the bundle pass."""
    records = [
        _record(0 * STEP, False),
        _record(1 * STEP, True),                  # single frame
        _record(2 * STEP, False),
        _record(3 * STEP, True),                  # sustained, three steps
        _record(4 * STEP, True),
        _record(5 * STEP, True),
        _record(6 * STEP, False),
        _record(7 * STEP, True),                  # another single frame
        _record(8 * STEP, False),
    ]
    intervals, _, _ = recorder.contact_intervals(records, 'target_box_a', [PUSHER])
    assert len(intervals) == 3
    spans = [iv['end_sim_ns'] - iv['start_sim_ns'] for iv in intervals]
    assert spans == [STEP, 3 * STEP, STEP]
    assert all(s > 0 for s in spans)
    assert _check_schema(intervals) == []


def test_no_fabricated_duration_when_step_ns_is_absent():
    """A record with no step_ns must not invent one; the span stays what the data says."""
    rec = _record(STEP, True)
    del rec['step_ns']
    intervals, _, _ = recorder.contact_intervals([rec], 'target_box_a', [PUSHER])
    assert len(intervals) == 1
    assert intervals[0]['end_sim_ns'] == intervals[0]['start_sim_ns']
    # The schema correctly still rejects this underspecified record - we did not
    # loosen the rule, and we did not pretend to know a duration we were not given.
    assert any('interval' in p for p in _check_schema(intervals))


def test_interval_representation_is_versioned():
    """Historical bundles have no such field, so a re-evaluation stays distinguishable."""
    assert recorder.CONTACT_INTERVAL_REPRESENTATION == 'half_open_per_physics_step_v2'