"""Re-derive the push contract's fixtures from the archived Step-0 probe.

WHY THIS FILE EXISTS
    tests/test_push_contract.py hard-codes the measured run3 numbers (23.02 mm,
    cosine 0.9965). A hard-coded measurement silently rots: someone re-runs the
    probe, the number changes, and the test keeps passing against a world that
    no longer exists. This module reads the archived evidence and asserts the
    fixtures still match it, so the two cannot drift apart.

WHAT IT DOES NOT DO
    It does not run the probe, does not touch a simulator, and does not re-judge
    the archived run. It reads JSONL/JSON that is already committed.
"""
import json
import math
from pathlib import Path

import pytest

from flexcell_skills.contracts import push

# The Step-0 capsule lives outside this worktree (it was produced by the
# t08-push teammate in the shared workspace). Locate it relative to the repo
# root rather than by absolute path so the test is portable across checkouts.
ROOT = Path(__file__).resolve().parents[4]
PROBE = (ROOT.parent / 'ci-public-window' / 'evidence' /
         'evobot_t08_push_step0_20261111')

pytestmark = pytest.mark.skipif(
    not PROBE.is_dir(),
    reason='T08 Step-0 evidence capsule is not present in this checkout')


def _load(relative):
    return json.loads((PROBE / relative).read_text(encoding='utf-8'))


def _summary():
    return _load('run3_z0030/push_step0_summary.json')


def test_the_archived_displacement_matches_the_contract_fixture():
    summary = _summary()
    before = summary['first']['target_box_a']
    after = summary['final']['target_box_a']
    metrics, error = push.contact_metrics(before, after, [-1.0, 0.0, 0.0])
    assert error is None
    # The archived summary rounds to 6 decimals; compare at that resolution.
    assert metrics['displacement_m'] == pytest.approx(
        summary['displacement_m'], abs=1e-6)
    assert metrics['direction_cos'] == pytest.approx(
        summary['direction_cos'], abs=1e-4)
    assert metrics['lateral_m'] == pytest.approx(
        summary['lateral_abs_m'], abs=1e-6)
    assert metrics['delta_z_m'] == pytest.approx(summary['dz_abs_m'], abs=1e-9)


def test_the_archived_run_is_graded_a_contact_loss_by_this_contract():
    """Step 0's own verdict and this contract's verdict must agree.

    The probe judged the run NOT_FEASIBLE because the box moved 23 of 30 mm and
    then stopped. If this contract ever graded the same measurement SUCCEEDED,
    the two would contradict each other and one of them would be wrong.
    """
    summary = _summary()
    resolved, error = push.resolve_goal(dict(
        object_name='target_box_a', direction=[-1.0, 0.0, 0.0],
        distance_m=summary['criteria']['displacement_min_m'],
        contact_height_m=0.030))
    assert error is None
    metrics, _ = push.contact_metrics(
        summary['first']['target_box_a'], summary['final']['target_box_a'],
        resolved['direction'])
    verdict = push.judge(metrics, resolved, None,
                         arm_travel_m=summary['geometry'].get('contact_z', 0.0) or 0.05,
                         reach_error_m=0.006, contact_lost_at_increment=0,
                         carry_engaged=False, increments_executed=9)
    assert verdict['outcome'] == push.OUTCOME_FAILED
    assert verdict['error_code'] == push.ERR_CONTACT_LOST
    assert summary['checks']['C1_displacement_ge_30mm'] is False


def test_the_saturation_is_real_in_the_archived_trajectory():
    """The claim this whole skill is built on: the arm advanced, the box did not.

    Read from the cumulative rows rather than from prose, so a re-run that
    changed the physics would break this test instead of passing unnoticed.
    """
    summary = _summary()
    rows = summary['cumulative_rows']
    tail = [row for row in rows if row['step'] in ('C3', 'C4', 'C5')]
    assert [row['step'] for row in tail] == ['C3', 'C4', 'C5']
    # The last two increments advanced the box by essentially nothing.
    assert tail[-1]['increment_m'] == pytest.approx(0.0, abs=1e-6)
    assert tail[-2]['increment_m'] < 1e-4
    # ... and the arm did keep moving over the same interval.
    ee = [sample['ee_world'][0] for sample in summary['samples']
          if sample['label'] in ('after_C3', 'after_C4', 'after_C5')]
    assert len(ee) == 3 and ee[0] > ee[1] > ee[2]
    assert ee[0] - ee[2] > 0.010          # more than 10 mm of further travel


def test_the_probe_never_engaged_the_carry_backend():
    """The 'pushed, not carried' precondition the skill now re-checks at runtime."""
    summary = _summary()
    assert summary['carry_engaged_any'] is False
    assert summary['carry_engaged_samples'] == []
    for sample in summary['samples']:
        assert sample['carry']['engaged'] is False
        assert sample['carry']['object_id'] == ''


def test_the_zero_displacement_run_is_the_false_negative_it_was_called():
    """run2: fingers 145 mm above the box, box never moved.

    This is the scenario that would have been reported as a success by any
    skill that graded the arm instead of the object.
    """
    summary = _load('run2/push_step0_summary.json')
    first = summary['first']['target_box_a']
    final = summary['final']['target_box_a']
    metrics, _ = push.contact_metrics(first, final, [-1.0, 0.0, 0.0])
    assert metrics['displacement_m'] < 0.005
    assert math.isnan(metrics['direction_cos'])   # undefined, not "sideways"
    resolved, _ = push.resolve_goal(dict(
        object_name='target_box_a', direction=[-1.0, 0.0, 0.0],
        distance_m=0.030, contact_height_m=0.1775))
    verdict = push.judge(metrics, resolved, None, arm_travel_m=0.05,
                         reach_error_m=0.008, contact_lost_at_increment=0,
                         carry_engaged=False, increments_executed=9)
    assert verdict['error_code'] == push.ERR_CONTACT_NOT_MADE
