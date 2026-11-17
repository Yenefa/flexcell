"""The trajectory this card emits must actually satisfy evaluate.py v0.4.0.

WHY THIS TEST RUNS THE REAL EVALUATOR
    Producing a JSON blob called "trajectory" proves nothing. The question is
    whether the REAL frozen evaluator accepts it and reaches the right verdict.
    So this test imports benchmark/evaluators/evaluate.py itself and feeds it
    the exact structure evobot_visual_vs_truth.py writes.

    This file does not modify the evaluator, does not restate its thresholds,
    and does not duplicate its logic. It checks COMPATIBILITY - that the
    evidence this card produces is shaped the way the clause requires.

WHY IT MATTERS
    v0.4.0's push clause FAILS CLOSED: no trajectory means the clause is False,
    never True. If this card emitted a slightly wrong shape, T08 could never
    pass no matter how correct the robot was, and the failure would look like a
    robot problem rather than a plumbing one.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
EVALUATOR = ROOT / 'benchmark' / 'evaluators' / 'evaluate.py'

# The pairing tool is an acceptance script, not a package, so it is loaded by
# path. Two layouts are searched because the card that owns it has lived in two
# places. WHY THE ORDER: the card was moved INTO this repository, which is what
# makes this file runnable in a plain checkout and in CI at all; the sibling
# `ci-public-window` checkout is the maintainer's older layout and is kept only
# as a fallback, so an existing working copy does not turn red on the day of the
# move.
SCRIPT_CANDIDATES = (
    ROOT / 'setup' / 'acceptance' / 'evobot_visual_capture_20261111' /
    'scripts' / 'evobot_visual_vs_truth.py',
    ROOT.parent / 'ci-public-window' / 'scripts' / 'evobot_visual_vs_truth.py',
)


def resolve_script():
    """The pairing tool this checkout carries, or None when it carries neither.

    WHY THE LOAD IS NOT DONE HERE
        A module-level load turns a sparse checkout (no `setup/acceptance`) into
        a FileNotFoundError during collection. That reads as "this test file is
        broken" instead of "this checkout does not carry the fixture", and it
        takes the whole collection down with it.
    """
    for candidate in SCRIPT_CANDIDATES:
        if candidate.is_file():
            return candidate
    return None


SCRIPT = resolve_script()

SCRIPT_MISSING = ('evobot_visual_vs_truth.py is not in this checkout; looked '
                  'for ' + ' and '.join(str(candidate)
                                        for candidate in SCRIPT_CANDIDATES))

# Only the evaluator decides whether this file can run at all. The pairing tool
# is needed by the five cases that call pairing_module(), and that call skips
# with SCRIPT_MISSING on its own - so a checkout without setup/acceptance still
# runs the three cases about the evaluator itself instead of skipping them too.
pytestmark = pytest.mark.skipif(not EVALUATOR.is_file(),
                                reason='frozen evaluator not present')


def evaluator():
    spec = importlib.util.spec_from_file_location('frozen_evaluate', EVALUATOR)
    loaded = importlib.util.module_from_spec(spec)
    sys.modules['frozen_evaluate'] = loaded
    spec.loader.exec_module(loaded)
    return loaded


def pairing_module():
    """Imported on first use, never at collection time.

    A missing tool is a skip with the paths that were searched, not an error:
    the absence of an acceptance artefact is not a failing assertion in this
    file's subject (the evaluator's compatibility rules).
    """
    if SCRIPT is None:
        pytest.skip(SCRIPT_MISSING)
    spec = importlib.util.spec_from_file_location('evobot_visual_vs_truth', SCRIPT)
    loaded = importlib.util.module_from_spec(spec)
    sys.modules['evobot_visual_vs_truth'] = loaded
    spec.loader.exec_module(loaded)
    return loaded


def push_spec():
    """A minimal push spec in the REAL shape evaluate.py consumes.

    Field names taken from evaluate.py itself (objects[].initial_pose,
    zones[], expected_goal.push) rather than invented: a test using a made-up
    shape would prove nothing about compatibility.
    """
    return {
        'task_id': 'T08', 'template_id': 'push',
        'objects': [{'name': 'target_box_a',
                     'initial_pose': [0.22, 0.0, 0.0175]}],
        'zones': [],
        'expected_goal': {'push': {'target_box_a': {
            'direction': [-1.0, 0.0, 0.0],
            'min_displacement_m': 0.02,
            'max_displacement_m': 0.04,
            'max_vertical_m': 0.02,
            'min_direction_cosine': 0.9,
            'max_lift_during_m': 0.005,
        }}},
    }


def frame(captured_wall_ns, x, z):
    return dict(frame='/tmp/f.png', captured_wall_ns=captured_wall_ns,
                objects={'target_box_a': [x, 0.0, z]})


def final_state(trajectory, x=0.19):
    return {
        'agent_claimed_success': True,
        'objects': {'target_box_a': [x, 0.0, 0.0175]},
        'trajectory': trajectory,
    }


# --------------------------------------------------- the clause fails closed
def test_without_a_trajectory_the_push_clause_fails():
    """The reason this card must emit one: absence is not evidence."""
    report = evaluator().evaluate(push_spec(), final_state({}))
    assert report['passed'] is False
    clause = report['clauses'][0]
    assert clause['ok'] is False
    # The reason lives in the clause's evidence block, and names the missing
    # evidence rather than blaming the robot.
    evidence = clause['evidence']
    assert evidence.get('trajectory_required') is True
    assert 'no trajectory' in evidence['reason']


def test_a_grasp_carry_place_is_caught_by_the_trajectory():
    """The mis-grade v0.4.0 exists to prevent: same end state, lifted mid-way."""
    report = evaluator().evaluate(
        push_spec(), final_state({'target_box_a': {'max_z_m': 0.12}}))
    assert report['passed'] is False
    assert 'push' in report['failed_clauses'][0]


def test_a_genuine_push_passes_with_the_trajectory():
    report = evaluator().evaluate(
        push_spec(), final_state({'target_box_a': {'max_z_m': 0.018}}))
    assert report['passed'] is True, report['clauses']


# ------------------------------------ our emitted shape satisfies the clause
def test_the_trajectory_this_card_emits_is_accepted_by_the_evaluator():
    """End to end: pairing pairs -> our trajectory -> real evaluator -> pass."""
    pairing = pairing_module()
    pairs = [frame(1_000_000_000, 0.220, 0.0175),
             frame(1_500_000_000, 0.210, 0.0175),
             frame(2_000_000_000, 0.200, 0.0176),
             frame(2_500_000_000, 0.190, 0.0175)]
    trajectory = pairing.trajectory_from_pairs(pairs)
    assert 'target_box_a' in trajectory
    report = evaluator().evaluate(push_spec(), final_state(trajectory))
    assert report['passed'] is True, report['clauses']


def test_our_trajectory_still_catches_a_lift_between_frames():
    """If the object really rose during a captured frame, we must report it."""
    pairing = pairing_module()
    pairs = [frame(1_000_000_000, 0.220, 0.0175),
             frame(1_500_000_000, 0.200, 0.1200),   # picked up
             frame(2_000_000_000, 0.190, 0.0175)]
    trajectory = pairing.trajectory_from_pairs(pairs)
    assert trajectory['target_box_a']['max_z_m'] == pytest.approx(0.12)
    report = evaluator().evaluate(push_spec(), final_state(trajectory))
    assert report['passed'] is False


# ------------------------------------------------------- honest bookkeeping
def test_the_trajectory_states_how_much_motion_could_hide_between_frames():
    """max_z over SAMPLES is not max_z over motion, and the record says so."""
    pairing = pairing_module()
    pairs = [frame(1_000_000_000, 0.220, 0.0175),
             frame(4_000_000_000, 0.190, 0.0175)]
    trajectory = pairing.trajectory_from_pairs(pairs)['target_box_a']
    assert trajectory['sample_count'] == 2
    assert trajectory['max_sample_gap_s'] == pytest.approx(3.0)
    assert 'not' in trajectory['limit'] and '3.000s' in trajectory['limit']


def test_frames_without_truth_do_not_invent_a_trajectory():
    pairing = pairing_module()
    pairs = [dict(frame='/tmp/a.png', captured_wall_ns=1_000_000_000,
                  objects={})]
    assert pairing.trajectory_from_pairs(pairs) == {}


def test_trajectory_is_json_safe(tmp_path):
    pairing = pairing_module()
    pairs = [frame(1_000_000_000, 0.220, 0.0175),
             frame(2_000_000_000, 0.190, 0.0175)]
    report = pairing.build_report(pairs, [], 2, 2.0)
    text = json.dumps(report, allow_nan=False)
    assert 'NaN' not in text
    assert report['trajectory']['target_box_a']['max_z_m'] == pytest.approx(0.0175)
