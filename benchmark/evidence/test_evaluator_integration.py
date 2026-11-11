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
