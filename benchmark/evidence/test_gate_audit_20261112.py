"""Adversarial gate-audit tests for benchmark/evidence/verify.py v1.0.0.

WHY THIS FILE EXISTS SEPARATELY FROM test_verifier.py
    test_verifier.py proves each gate can REJECT a bundle that is broken in the
    way the gate is designed for. It does not ask the mirror question: can a gate
    be made to ACCEPT a bundle it should reject? A gate that passes everything is
    worse than a missing gate, because the output still says PROVEN.

WHAT EACH TEST ASSERTS
    Every test below encodes a property the verifier CLAIMS to hold, and asserts
    that it actually holds. Tests marked xfail(strict=True) are KNOWN DEFECTS:
    they are written as the property that SHOULD hold, so the day the defect is
    fixed in a new version the test flips to XPASS and strict=True turns that into
    a failure - forcing someone to come back and promote it to a plain assert.

    That is the opposite of the usual xfail usage: these are not "expected to
    fail", they are "must not silently start passing". Do not delete them.

COUNTERPARTS
    Every xfail here has a numbered finding F<n> in
    setup/acceptance/evobot_t08_gate_audit_20261112/README.md with a standalone
    reproducer under reproducers/repro_9gate_audit.py.
"""
import copy
import json
import math
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(WT, 'benchmark', 'evaluators'))

import fixtures                                            # noqa: E402
import schema                                              # noqa: E402
import verify                                              # noqa: E402
import evaluate as ev                                      # noqa: E402

SPEC2000 = os.path.join(WT, 'benchmark', 'tasks', 't08_dev',
                        'T08-push-seed2000.json')
REST = 0.0175
STEP = 5_000_000
T0 = 10_000_000_000
N = 40
# The limits evaluate.py v0.5.0 actually passes (evaluate.py:326-330).
EVAL_LIMITS = {'max_lift_during_m': 0.020, 'max_aperture_change_rad': 0.002,
               'protected_move_m': 0.005}


def judge(bundle, limits=None, terminal=None):
    return verify.verify(
        bundle,
        fixtures.terminal_verdict(True) if terminal is None else terminal,
        fixtures.limits() if limits is None else limits)


def spec(path=SPEC2000):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def carried_bundle(rest_declared, carry_z, dx=-0.003):
    """A target that rides at carry_z for the whole run, never touching the
    table. The declared rest height is a free parameter - that is the defect."""
    b = fixtures.base_bundle()
    b['objects'] = {
        'target_box_a': {'role': 'target', 'samples': None, 'sample_count': N,
                         'dropped_samples': 0, 'max_gap_ns': STEP},
        'target_box_b': {'role': 'protected', 'samples': None, 'sample_count': N,
                         'dropped_samples': 0, 'max_gap_ns': STEP},
    }
    b['task'].update(target_object='target_box_a', protected_object='target_box_b',
                     rest_height_m=rest_declared, task_id='T08-push-seed2000',
                     task_sha256=schema.sha256_file(SPEC2000))
    b['objects']['target_box_a']['samples'] = fixtures.trajectory(
        T0, N, carry_z, 0.22, dx)
    prot = fixtures.trajectory(T0, N, REST, 0.0, 0.0)
    b['objects']['target_box_b']['samples'] = [
        [q[0], q[1], q[2], 0.20, -0.18, REST] + q[6:] for q in prot]
    b['gripper']['span'] = [[1_000_000_000 + STEP * i, 0.0] for i in range(N)]
    b['contacts'].update(pusher_links=['arm_link_6'],
                         intervals=[{'start_sim_ns': T0 + STEP * 5,
                                     'end_sim_ns': T0 + STEP * 39,
                                     'other': 'arm_link_6'}])
    b['attachment'] = {'events': 0, 'attached_during_window': False}
    b['teleport']['max_single_step_jump_m'] = verify._observed_max_jump(b)
    b['manifest']['bundle_sha256'] = schema.bundle_sha256(b)
    return b


def pushed_state(bundle, max_z, x=0.22 - 0.003 * 39):
    return {'objects': {'target_box_a': [x, 0.0, REST, 0.0],
                        'target_box_b': [0.20, -0.18, REST, 0.0]},
            'trajectory': {'target_box_a': {'max_z_m': max_z}},
            'evidence': bundle}


# ===================================================================== F1
# THE HEADLINE DEFECT: a pure carry passes all nine gates.
@pytest.mark.xfail(strict=True, reason=(
    'F1: a constant-height carry passes every gate when the bundle declares '
    'rest_height_m = the carry height. verify.py:141-143 and :209 both '
    'subtract that self-declared value.'))
def test_f1_a_carried_object_must_not_be_reported_as_pushed():
    carry_z = REST + 0.050
    b = carried_bundle(rest_declared=carry_z, carry_z=carry_z)
    v = ev.evaluate(spec(), pushed_state(b, REST))
    assert v['passed'] is False, (
        'a 50 mm-high carry was graded PUSHED with no failed gate')


def test_f1b_control_the_same_carry_with_honest_rest_is_rejected():
    """Control: the bypass needs the fabricated rest and nothing else."""
    carry_z = REST + 0.050
    b = carried_bundle(rest_declared=REST, carry_z=carry_z)
    v = ev.evaluate(spec(), pushed_state(b, carry_z))
    assert v['passed'] is False
    assert 'table_support' in v['evidence']['failed_gates']


# ===================================================================== F2
@pytest.mark.xfail(strict=True, reason=(
    'F2: schema.py:76 only checks _finite() on rest_height_m; it is never '
    'compared to spec.objects[].initial_pose[2].'))
def test_f2_rest_height_must_agree_with_the_task_spec():
    b = fixtures.base_bundle()
    b['task']['rest_height_m'] = 0.9999
    assert schema.validate(b) != [], (
        'a declared rest height 982 mm from the spec was accepted')


# ===================================================================== F3
@pytest.mark.xfail(strict=True, reason=(
    'F3: evaluate.py:227-238 trusts observation.trajectory.max_z_m; the '
    'bundle carries an independent measurement that is never cross-checked.'))
def test_f3_observation_max_z_must_agree_with_the_evidence_bundle():
    lift = 0.008
    b = carried_bundle(REST, REST)
    samples = fixtures.trajectory(T0, N, REST, 0.22, -0.003)
    for i, s in enumerate(samples):
        s[5] = REST + lift * math.sin(math.pi * i / (N - 1.0))
    b['objects']['target_box_a']['samples'] = samples
    b['teleport']['max_single_step_jump_m'] = verify._observed_max_jump(b)
    b['manifest']['bundle_sha256'] = schema.bundle_sha256(b)
    v = ev.evaluate(spec(), pushed_state(b, REST))
    assert v['passed'] is False, (
        'an 8 mm lift was hidden by reporting max_z_m = rest')


# ===================================================================== F4
@pytest.mark.xfail(strict=True, reason=(
    'F4: schema.py:279 only checks isinstance(bundle_sha256, str); the digest '
    'is never recomputed, so any post-hoc edit is undetectable.'))
def test_f4_a_bundle_edited_after_sealing_must_be_rejected():
    b = fixtures.base_bundle()
    stored = b['manifest']['bundle_sha256']
    b['run']['run_id'] = 'a-run-that-never-happened'
    assert schema.bundle_sha256(b) == stored or not judge(b)['passed'], (
        'bundle contents changed but the stale digest was accepted')


# ===================================================================== F5
@pytest.mark.xfail(strict=True, reason=(
    'F5: verify.py:105 calls schema.validate(bundle) with no files argument, '
    'so the manifest completeness check never runs on the production path.'))
def test_f5_an_uncovered_input_file_must_fail_on_the_production_path():
    b = fixtures.base_bundle()
    assert not judge(b, files=['ghost.jsonl'])['passed']


# ===================================================================== F6
@pytest.mark.xfail(strict=True, reason=(
    'F6: nothing binds a bundle to a trial - run_id, nonce and task_sha256 are '
    'never compared to the observation, so one bundle replays everywhere.'))
def test_f6_a_bundle_must_not_be_reusable_across_trials():
    good = carried_bundle(REST, REST)
    verdicts = [ev.evaluate(spec(), pushed_state(good, REST, x=0.12 + 0.001 * t))
                ['passed'] for t in range(5)]
    assert not all(verdicts), 'one bundle passed 5 different trials'


# ===================================================================== F7
@pytest.mark.xfail(strict=True, reason=(
    'F7: run.execution_window is validated for ordering but never used to '
    'bound or filter the samples.'))
def test_f7_the_execution_window_must_contain_the_samples():
    b = carried_bundle(REST, REST)
    b['run']['execution_window'] = {'start_sim_ns': 1, 'end_sim_ns': 2,
                                    'start_mono_ns': 1, 'end_mono_ns': 2}
    b['manifest']['bundle_sha256'] = schema.bundle_sha256(b)
    assert not judge(b)['passed']


# ===================================================================== F8
@pytest.mark.xfail(strict=True, reason=(
    'F8: verify.py:329 computes travel = max - min, which is 0 for a '
    'single-sample span. A one-sample span cannot rule out a grasp.'))
def test_f8_a_single_sample_gripper_span_must_be_refused():
    b = fixtures.base_bundle()
    b['gripper']['span'] = [[1_000_000_000, 0.06]]
    gate = next(g for g in judge(b)['gates'] if g['gate'] == 'gripper')
    assert gate['ok'] is False


# ===================================================================== F9
@pytest.mark.xfail(strict=True, reason=(
    'F9: verify.py:235 reads pusher_links from the bundle it is judging; any '
    'body name, including the floor, can be declared a pusher.'))
def test_f9_pusher_links_must_come_from_an_allow_list():
    b = fixtures.base_bundle()
    floor = 'ground_plane::link::collision'
    b['contacts']['pusher_links'] = [floor]
    b['contacts']['intervals'] = [{'start_sim_ns': T0,
                                   'end_sim_ns': T0 + STEP * 39, 'other': floor}]
    assert not judge(b)['passed']


# ==================================================================== F10
@pytest.mark.xfail(strict=True, reason=(
    'F10: recorder.py:172 declares max_gap_ns = max(observed_gap, 1), so '
    'schema.py:164 compares the gap against itself.'))
def test_f10_a_lossy_log_must_be_reported_as_a_gap():
    import recorder
    recs = [{'sim_ns': T0 + STEP * i, 'monotonic_ns': T0 + STEP * i,
             'objects': {'target_box_a': {'pose': [0.22, 0.0, REST, 0, 0, 0, 1]},
                         'target_box_b': {'pose': [0.20, -0.18, REST, 0, 0, 0, 1]}}}
            for i in range(80) if not (20 <= i < 60)]
    samples, dropped, gap = recorder.trajectory_from_physics(recs, 'target_box_a')
    entry = {'role': 'target', 'samples': samples,
             'sample_count': len(samples), 'dropped_samples': dropped,
             'max_gap_ns': max(gap, 1)}
    assert schema._problems_one_trajectory('t', entry) != [], (
        '40 of 80 steps lost, reported as no problem')


# ==================================================================== F11
@pytest.mark.xfail(strict=True, reason=(
    'F11: recorder.py:84 numbers samples by enumerate() index, not physics '
    'step, so schema contiguity checks can never fire on a lossy log.'))
def test_f11_sequence_numbers_must_track_physics_steps():
    import recorder
    recs = [{'sim_ns': T0 + STEP * i, 'monotonic_ns': T0 + STEP * i,
             'objects': {'target_box_a': {'pose': [0.22, 0.0, REST, 0, 0, 0, 1]},
                         'target_box_b': {'pose': [0.20, -0.18, REST, 0, 0, 0, 1]}}}
            for i in range(80) if i % 2 == 0]
    samples, _dropped, _gap = recorder.trajectory_from_physics(recs,
                                                              'target_box_a')
    contiguous = all(samples[i + 1][0] == samples[i][0] + 1
                     for i in range(len(samples) - 1))
    assert contiguous is False, 'half the physics steps lost, sequence contiguous'


# ==================================================================== F12
@pytest.mark.xfail(strict=True, reason=(
    'F12: dropped_samples is range-checked (schema.py:131) but no gate reads '
    'it, so a bundle can declare 937 dropped samples and still pass.'))
def test_f12_a_bundle_that_declares_dropped_samples_must_not_pass():
    b = fixtures.base_bundle()
    b['objects']['block-1']['dropped_samples'] = 937
    assert not judge(b)['passed']


# ==================================================================== F13
def test_f13_the_verifier_tests_must_exercise_the_production_limits():
    """The limit evaluate.py passes must be the limit the tests exercise.

    fixtures.limits() uses 0.005; evaluate.py:327 passes 0.020. Between 8 mm and
    9.5 mm of lift the two disagree, so every verifier unit test can be green
    while the production path admits a lift the tests believe is rejected.
    This test PINS the current divergence; it must be inverted when fixed.
    """
    lift = 0.008
    b = fixtures.base_bundle()
    target = b['task']['target_object']
    rest = b['task']['rest_height_m']
    samples = fixtures.trajectory(T0, 40, rest, 0.0, 0.005)
    for i, s in enumerate(samples):
        s[5] = rest + lift * math.sin(math.pi * i / 39.0)
    b['objects'][target]['samples'] = samples
    assert judge(b)['passed'] is False, 'fixtures limit should reject 8 mm'
    assert verify.verify(b, fixtures.terminal_verdict(True),
                         EVAL_LIMITS)['passed'] is True, (
        'production limit should accept 8 mm - if this now fails, the limits '
        'have been unified and this test should assert equality instead')


# ==================================================================== F14
def test_f14_overshoot_and_undershoot_are_indistinguishable():
    """Pins the evidence-quality defect in evaluate.py:241.

    Both a 4 mm undershoot and a 157 mm overshoot produce the identical
    failed_clauses entry. The numbers survive in clause evidence, so the data is
    there; only the verdict is ambiguous. Asserted here so a future fix that adds
    a distinct reason field is visible as a change.
    """
    def clause_for(dx):
        b = carried_bundle(REST, REST, dx=dx)
        v = ev.evaluate(spec(), pushed_state(b, REST, x=0.22 + dx * 39))
        return (v['failed_clauses'],
                [c for c in v['clauses'] if c['clause'].startswith('push:')][0])
    under_fc, under = clause_for(-0.0001)
    over_fc, over = clause_for(-0.004026)
    assert under_fc == over_fc == ['push:target_box_a'], (
        'the two failures are now distinguishable - update the finding')
    assert under['evidence']['displacement_m'] < 0.03
    assert over['evidence']['displacement_m'] > 0.15
    assert over['evidence']['inside_zone'] is True
    assert under['evidence']['inside_zone'] is False


# ==================================================================== F15
@pytest.mark.xfail(strict=True, reason=(
    'F15: verify.py:358 only range-checks attachment.events; it is never '
    'cross-checked against attached_during_window.'))
def test_f15_attachment_events_must_agree_with_the_window_flag():
    b = fixtures.base_bundle()
    b['attachment'] = {'events': 5, 'attached_during_window': False}
    gate = next(g for g in judge(b)['gates'] if g['gate'] == 'no_attachment')
    assert gate['ok'] is False


# ==================================================================== F16
@pytest.mark.xfail(strict=True, reason=(
    'F16: observe_from_run.py:147-150 keeps only 5 keys, dropping the evidence '
    'bundle and the trajectory. The production bridge cannot deliver evidence.'))
def test_f16_the_observation_bridge_must_carry_the_evidence_bundle():
    import observe_from_run as ofr
    obs = {'objects': {'target_box_a': [0.12, 0.0, REST, 0.0]},
           'move_sequence': [], 'agent_claimed_success': True,
           'agent_claim_source': 'measured', 'visits': {},
           'trajectory': {'target_box_a': {'max_z_m': REST}},
           'evidence': fixtures.base_bundle()}
    kept = ofr.strip_diagnostics(obs)
    assert 'evidence' in kept and 'trajectory' in kept


# ============================================================ the positives
def test_the_honest_baseline_still_passes():
    """Control: none of the above may be achieved by breaking the verifier."""
    r = judge(fixtures.base_bundle())
    assert r['passed'] is True, r['failure_reason']
    assert r['physical_outcome'] == 'PUSHED'


def test_all_nine_gates_are_reported_exactly_once():
    names = [g['gate'] for g in judge(fixtures.base_bundle())['gates']]
    assert len(names) == len(set(names)) == 9
    assert set(names) == {'terminal', 'trajectory', 'table_support',
                          'protected_unmoved', 'no_lift', 'pusher_contact',
                          'gripper', 'no_attachment', 'no_teleport'}


def test_the_frozen_numbers_are_still_frozen():
    s = spec()
    push = s['expected_goal']['push']['target_box_a']
    assert push['min_displacement_m'] == 0.030
    assert push['max_displacement_m'] == 0.150
    assert push['max_vertical_m'] == 0.020
    assert push['min_direction_cosine'] == 0.9
    assert s['zones'][0]['radius'] == 0.06
    assert ev.EVALUATOR_VERSION == '0.5.0'
    assert verify.VERIFIER_VERSION == '1.0.0'