"""v0.5.0 integration: the terminal verdict is no longer the whole verdict.

These tests exist because the integration itself is the risky part, not the
verifier. verify.py is thoroughly tested on its own; what is untested is that
evaluate.py actually calls it, that it fails closed when it cannot, and that
T01-T06 are untouched.

A silent regression here would be invisible: every T08 run would go back to
being graded on terminal geometry while the evidence module still passed its
own tests.
"""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.dirname(os.path.dirname(HERE))
EVAL = os.path.join(WT, 'benchmark', 'evaluators', 'evaluate.py')
T08 = os.path.join(WT, 'benchmark', 'tasks', 't08_dev', 'T08-push-seed2000.json')
T01 = os.path.join(WT, 'benchmark', 'tasks', 'train', 'T01-train-seed1000.json')

sys.path.insert(0, os.path.join(WT, 'benchmark', 'evidence'))
sys.path.insert(0, WT)


def _run(spec, state, tmp_path):
    p = tmp_path / 'state.json'
    p.write_text(json.dumps(state))
    out = subprocess.run([sys.executable, EVAL, spec, str(p)],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def _pushed_state(**extra):
    st = {'objects': {'target_box_a': [0.12, 0.0, 0.0175, 0.0],
                      'target_box_b': [0.2, -0.18, 0.0175, 0.0]},
          'trajectory': {'target_box_a': {'max_z_m': 0.018}}}
    st.update(extra)
    return st


def test_the_terminal_state_alone_is_no_longer_enough(tmp_path):
    """Terminal passes, no evidence bundle: the whole point of v0.5.0."""
    d = _run(T08, _pushed_state(), tmp_path)
    assert d['terminal_passed'] is True
    assert d['failed_clauses'] == []
    assert d['passed'] is False
    assert d['evidence']['evidence_status'] == 'INCOMPLETE_OR_INVALID_EVIDENCE'
    assert 'no evidence bundle' in d['evidence']['failure_reason']


def test_missing_evidence_reports_unknown_not_a_robot_failure(tmp_path):
    """'We cannot tell' must not be reported as 'the robot did not push'."""
    d = _run(T08, _pushed_state(), tmp_path)
    assert d['evidence']['physical_outcome'] == 'UNKNOWN'


def test_a_malformed_bundle_fails_closed(tmp_path):
    d = _run(T08, _pushed_state(evidence={'nonsense': True}), tmp_path)
    assert d['passed'] is False
    assert d['evidence']['evidence_status'] == 'INCOMPLETE_OR_INVALID_EVIDENCE'


def test_evidence_cannot_rescue_a_failed_terminal_state(tmp_path):
    """Evidence is a conjunction, never an override."""
    from fixtures import base_bundle
    st = {'objects': {'target_box_a': [0.22, 0.0, 0.0175, 0.0],
                      'target_box_b': [0.2, -0.18, 0.0175, 0.0]},
          'evidence': base_bundle()}
    d = _run(T08, st, tmp_path)
    assert d['terminal_passed'] is False
    assert d['passed'] is False


def test_t01_has_no_evidence_requirement_and_keeps_its_old_shape(tmp_path):
    """Every frozen T01-T06 result must be unaffected by v0.5.0."""
    spec = json.load(open(T01))
    st = {'objects': {o['name']: list(o['initial_pose']) for o in spec['objects']}}
    d = _run(T01, st, tmp_path)
    assert d['evaluator_version'] == '0.5.0'
    assert 'evidence' not in d


def test_version_was_actually_bumped():
    src = open(EVAL, encoding='utf-8').read()
    assert 'EVALUATOR_VERSION = "0.5.0"' in src


def test_the_frozen_v030_copy_is_still_present_and_different():
    frozen = os.path.join(WT, 'setup', 'acceptance',
                          'evobot_audit_p0_fixes_20261111',
                          'evaluate_v0.3.0.FROZEN.py')
    assert os.path.exists(frozen), 'the v0.3.0 frozen copy must be preserved'
    src = open(frozen, encoding='utf-8').read()
    assert 'EVALUATOR_VERSION = "0.3.0"' in src


def test_the_30mm_threshold_is_untouched():
    """The gate this whole exercise keeps failing must not have moved."""
    spec = json.load(open(T08))
    push = spec['expected_goal']['push']['target_box_a']
    assert push['min_displacement_m'] == 0.030
    assert push['max_vertical_m'] == 0.020
    assert push['min_direction_cosine'] == 0.9

# ---------------------------------------------------------------------------
# The limits wiring bug.
#
# verify() needs three numeric limits. Handed None, each limit-dependent gate
# fails closed with 'no lift limit supplied', which is the correct behaviour for
# the gate and catastrophic for the caller: every genuine push graded
# NOT_PUSHED through evaluate.py, while the same bundle graded PUSHED when the
# unit tests called verify() directly with fixtures.limits().
#
# That is the worst shape a bug can take here -- 65 verifier tests green, the
# integration test suite green, and the only production path failing closed on
# every run. It was found by running a valid bundle through evaluate.py and
# comparing against a direct verify() call, not by reading either file.
# ---------------------------------------------------------------------------
def _valid_bundle():
    from fixtures import base_bundle
    return base_bundle()


def test_a_valid_push_passes_through_the_evaluator_not_just_through_verify(tmp_path):
    """The regression: a valid push must survive the real call path."""
    st = _pushed_state(evidence=_valid_bundle())
    d = _run(T08, st, tmp_path)
    assert d['terminal_passed'] is True
    assert d['evidence']['failed_gates'] if False else True  # gates live in evidence
    failed = [g['gate'] for g in d['evidence'].get('gates', []) if not g['ok']]
    assert failed == [], f'no gate should reject a valid push, got {failed}'
    assert d['passed'] is True
    assert d['evidence']['physical_outcome'] == 'PUSHED'
    assert d['evidence']['evidence_status'] == 'COMPLETE'


def test_the_lift_gate_still_bites_through_the_evaluator(tmp_path):
    """Fixing the wiring must not turn the gate off."""
    import math
    from fixtures import base_bundle, trajectory
    b = base_bundle()
    t = b['task']['target_object']
    rest = b['task']['rest_height_m']
    b['objects'][t]['samples'] = trajectory(
        10_000_000_000, 40, rest, 0.0, 0.005,
        lift=lambda i: 0.060 * math.sin(math.pi * i / 39.0))
    st = _pushed_state(evidence=b)
    d = _run(T08, st, tmp_path)
    assert d['passed'] is False
    failed = [g['gate'] for g in d['evidence'].get('gates', []) if not g['ok']]
    assert 'no_lift' in failed
