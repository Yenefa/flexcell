#!/usr/bin/env python3
"""Adversarial audit reproducers for benchmark/evidence/verify.py v1.0.0 (task-2).

Every finding in README.md is reproduced here as an executable assertion.
Run:  python3 repro_9gate_audit.py            (all findings)
      python3 repro_9gate_audit.py F1 F4      (selected)

DESIGN RULE: each finding must FAIL a property that the verifier claims to hold.
A finding that only "looks wrong" is not reported. Where the honest control
rejects and the fabricated one passes, both are run so the delta is visible.

No simulator, no network, no model calls. Pure offline analysis.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# reproducers/ -> evobot_t08_gate_audit_20261112/ -> acceptance/ -> setup/ -> repo
WT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(WT, 'benchmark', 'evidence'))
sys.path.insert(0, os.path.join(WT, 'benchmark', 'evaluators'))

import fixtures                                             # noqa: E402
import schema                                               # noqa: E402
import verify                                               # noqa: E402
import evaluate as ev                                       # noqa: E402

SPEC2000 = os.path.join(WT, 'benchmark', 'tasks', 't08_dev',
                        'T08-push-seed2000.json')
SPEC3000 = os.path.join(WT, 'benchmark', 'tasks', 't08_unseen',
                        'T08-push-seed3000.json')
REST = 0.0175          # T08 spec: target_box_a initial_pose[2], half a 35 mm cube
STEP = 5_000_000
T0 = 10_000_000_000
N = 40

# The limits evaluate.py v0.5.0 actually passes (evaluate.py:326-330).
EVAL_LIMITS = {'max_lift_during_m': 0.020,
               'max_aperture_change_rad': 0.002,
               'protected_move_m': 0.005}

RESULTS = []


def record(fid, claim, holds, detail):
    RESULTS.append((fid, claim, holds, detail))
    print('  [%s] %s' % ('PASS' if holds else 'FINDING', fid))
    print('        claim : %s' % claim)
    print('        detail: %s' % detail)


def spec(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def bundle_with(rest_declared, zfn, dx=-0.003, target='target_box_a',
                protected='target_box_b'):
    """A bundle whose target trace is produced by zfn(index) and whose
    declared rest height is rest_declared. The digest is recomputed, so the
    bundle is internally self-consistent - exactly what a fabricator would do."""
    b = fixtures.base_bundle()
    b['objects'] = {
        target: {'role': 'target', 'samples': None, 'sample_count': N,
                 'dropped_samples': 0, 'max_gap_ns': STEP},
        protected: {'role': 'protected', 'samples': None, 'sample_count': N,
                    'dropped_samples': 0, 'max_gap_ns': STEP},
    }
    b['task'].update(target_object=target, protected_object=protected,
                     rest_height_m=rest_declared, task_id='T08-push-seed2000',
                     task_sha256=schema.sha256_file(SPEC2000))
    samples = fixtures.trajectory(T0, N, REST, 0.22, dx)
    for i, s in enumerate(samples):
        s[5] = zfn(i)
    b['objects'][target]['samples'] = samples
    prot = fixtures.trajectory(T0, N, REST, 0.0, 0.0)
    b['objects'][protected]['samples'] = [
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


def state_with(bundle, max_z, x=0.22 - 0.003 * 39):
    return {'objects': {'target_box_a': [x, 0.0, REST, 0.0],
                        'target_box_b': [0.20, -0.18, REST, 0.0]},
            'trajectory': {'target_box_a': {'max_z_m': max_z}},
            'evidence': bundle}


# ---------------------------------------------------------------- F1
def f1_carry_as_push():
    """THE HEADLINE DEFECT. A pure carry passes every one of the 9 gates."""
    carry_z = REST + 0.050                      # rides 50 mm above the table
    b = bundle_with(rest_declared=carry_z, zfn=lambda i: carry_z)
    v = ev.evaluate(spec(SPEC2000), state_with(b, REST))
    zs = [s[5] for s in b['objects']['target_box_a']['samples']]
    record('F1',
           'a bundle whose object is CARRIED 50 mm above the table for the '
           'whole run must not be reported as PUSHED',
           not v['passed'],
           'passed=%r physical_outcome=%r failed_gates=%r | true z min=max=%.4f, '
           'table rest=%.4f, clearance=%.1f mm | declared rest=%.4f (spec %.4f)'
           % (v['passed'], v['evidence']['physical_outcome'],
              v['evidence']['failed_gates'], min(zs), REST,
              (min(zs) - REST) * 1000, b['task']['rest_height_m'], REST))


def f1b_carry_honest_control():
    """Control: the same carry with an HONEST rest height is rejected."""
    carry_z = REST + 0.050
    b = bundle_with(rest_declared=REST, zfn=lambda i: carry_z)
    v = ev.evaluate(spec(SPEC2000), state_with(b, carry_z))
    record('F1b',
           'control: the same carry with rest_height declared honestly is rejected',
           not v['passed'],
           'passed=%r failed_gates=%r (control behaves correctly; the bypass '
           'needs only the fabricated rest)'
           % (v['passed'], v['evidence']['failed_gates']))


# ---------------------------------------------------------------- F2
def f2_rest_height_unbound():
    """rest_height_m is checked only for finiteness, never against the spec."""
    b = fixtures.base_bundle()
    problems_honest = schema.validate(b)
    b['task']['rest_height_m'] = 0.9999
    problems_fake = schema.validate(b)
    record('F2',
           'schema must reject a declared rest_height_m that contradicts '
           'task.objects[].initial_pose[2]',
           problems_fake != problems_honest,
           'declared 0.9999 m (spec 0.0175 m) -> schema problems=%r; '
           'schema.py:76 tests _finite() only' % (problems_fake,))


# ---------------------------------------------------------------- F3
def f3_max_z_trusted():
    """evaluate.py trusts observation.trajectory.max_z_m, which the bundle
    contradicts. The bundle's own no_lift gate measures the real lift."""
    lift = 0.008
    b = bundle_with(rest_declared=REST,
                    zfn=lambda i: REST + lift * math.sin(math.pi * i / (N - 1.0)))
    honest = ev.evaluate(spec(SPEC2000), state_with(b, REST + lift))
    lying = ev.evaluate(spec(SPEC2000), state_with(b, REST))
    gate = [g for g in lying['evidence']['gates'] if g['gate'] == 'no_lift'][0]
    record('F3',
           'a run whose bundle shows an 8 mm lift must not pass by reporting '
           'max_z_m=rest in the observation',
           not lying['passed'],
           'reported max_z=%.4f -> terminal=%r passed=%r | same bundle '
           'reported honestly -> terminal=%r | the evidence layer measured '
           'max_lift=%.6f m independently (gate ok=%r)'
           % (REST, lying['terminal_passed'], lying['passed'],
              honest['terminal_passed'],
              gate['evidence']['max_lift_m'], gate['ok']))


# ---------------------------------------------------------------- F4
def f4_digest_never_recomputed():
    """manifest.bundle_sha256 is only type-checked, never recomputed."""
    # Tamper a field NO GATE READS, so the digest mismatch is the only signal.
    # (Tampering a coordinate would be caught by the teleport gate's
    # declared-vs-measured comparison, which would hide the digest defect.)
    b = fixtures.base_bundle()
    stored = b['manifest']['bundle_sha256']
    b['run']['run_id'] = 'a-run-that-never-happened'
    b['contacts']['all_partners_seen'] = ['ghost_link']
    recomputed = schema.bundle_sha256(b)
    v = verify.verify(b, fixtures.terminal_verdict(True), fixtures.limits())
    record('F4',
           'a bundle whose contents no longer match its stored '
           'bundle_sha256 must be rejected',
           stored == recomputed or not v['passed'],
           'stored=%s... recomputed=%s... equal=%r | schema problems=%r | '
           'verify passed=%r failed_gates=%r (schema.py:279 checks '
           'isinstance(str) only; bundle_sha256 is never recomputed)'
           % (stored[:10], recomputed[:10], stored == recomputed,
              schema.validate(b), v['passed'], v['failed_gates']))


# ---------------------------------------------------------------- F5
def f5_manifest_completeness_unused():
    """validate(files=...) exists but no production caller passes it."""
    b = fixtures.base_bundle()
    with_files = schema.validate(b, files=['physics.jsonl', 'ghost.jsonl'])
    without = schema.validate(b)
    record('F5',
           'an input file not covered by the manifest must be rejected on the '
           'production path',
           with_files != without,
           'validate(files=[ghost]) -> %r ; validate() -> %r ; verify.py:105 '
           'calls validate(bundle) with no files argument'
           % (with_files, without))


# ---------------------------------------------------------------- F6
def f6_evidence_replay():
    """One captured bundle is reusable across arbitrarily many trials."""
    good = bundle_with(REST, lambda i: REST)
    verdicts = []
    for trial in range(5):
        st = state_with(good, REST, x=0.12 + 0.001 * trial)
        verdicts.append(ev.evaluate(spec(SPEC2000), st)['passed'])
    record('F6',
           'a bundle captured for one trial must not be accepted for a '
           'different trial of the same task',
           not all(verdicts),
           'one bundle replayed across 5 trials with different final poses -> '
           'passed=%r | bundle run_id=%r is never compared to the trial'
           % (verdicts, good['run']['run_id']))


# ---------------------------------------------------------------- F7
def f7_window_decorative():
    """execution_window is never used to filter or bound the samples."""
    b = bundle_with(REST, lambda i: REST)
    b['run']['execution_window'] = {'start_sim_ns': 1, 'end_sim_ns': 2,
                                    'start_mono_ns': 1, 'end_mono_ns': 2}
    b['manifest']['bundle_sha256'] = schema.bundle_sha256(b)
    v = ev.evaluate(spec(SPEC2000), state_with(b, REST))
    record('F7',
           'a bundle whose execution window excludes all of its own samples '
           'must be rejected',
           not v['passed'],
           'window=1..2 ns, samples span %d ns -> passed=%r problems=%r'
           % (STEP * (N - 1), v['passed'], schema.validate(b)))


# ---------------------------------------------------------------- F8
def f8_gripper_single_sample():
    """The gripper gate passes on a span of one sample."""
    b = fixtures.base_bundle()
    b['gripper']['span'] = [[1_000_000_000, 0.06]]
    r = verify.verify(b, fixtures.terminal_verdict(True), fixtures.limits())
    g = [x for x in r['gates'] if x['gate'] == 'gripper'][0]
    record('F8',
           'a gripper span of one sample cannot rule out a close-carry-reopen '
           'and must be refused',
           not g['ok'],
           'span of 1 sample -> gate ok=%r travel=%r | verify.py:329 '
           'travel = max-min = 0 for n=1'
           % (g['ok'], g['evidence'].get('aperture_travel_rad')))


# ---------------------------------------------------------------- F9
def f9_pusher_links_self_declared():
    """pusher_links is taken from the bundle with no allow-list."""
    b = fixtures.base_bundle()
    floor = 'ground_plane::link::collision'
    b['contacts']['pusher_links'] = [floor]
    b['contacts']['intervals'] = [{'start_sim_ns': T0,
                                   'end_sim_ns': T0 + STEP * 39, 'other': floor}]
    r = verify.verify(b, fixtures.terminal_verdict(True), fixtures.limits())
    record('F9',
           'contact from a body that is not the robot must not satisfy the '
           'pusher-contact gate',
           not r['passed'],
           'declared %r as the pusher -> passed=%r failed=%r | verify.py:235 '
           'reads pusher_links from the bundle it is judging'
           % (floor, r['passed'], r['failed_gates']))


# ---------------------------------------------------------------- F10
def f10_max_gap_tautology():
    """recorder declares max_gap_ns = the observed max, so schema's check
    compares the gap to itself."""
    import recorder
    recs = []
    for i in range(80):
        if 20 <= i < 60:
            continue                          # 40 consecutive steps lost
        recs.append({'sim_ns': T0 + STEP * i, 'monotonic_ns': T0 + STEP * i,
                     'objects': {'target_box_a': {'pose': [0.22, 0.0, REST,
                                                          0, 0, 0, 1]},
                                 'target_box_b': {'pose': [0.20, -0.18, REST,
                                                           0, 0, 0, 1]}}})
    samples, dropped, gap = recorder.trajectory_from_physics(recs, 'target_box_a')
    entry = {'role': 'target', 'samples': samples, 'sample_count': len(samples),
             'dropped_samples': dropped, 'max_gap_ns': max(gap, 1)}
    problems = schema._problems_one_trajectory('t', entry)
    control = dict(entry, max_gap_ns=STEP)
    control_problems = schema._problems_one_trajectory('t', control)
    record('F10',
           'a log missing 40 of 80 physics steps must be reported as a gap',
           bool(problems),
           'dropped=%d observed gap=%d ns -> schema problems=%r | control '
           '(declared gap forced to %d) -> %r | recorder.py:172 writes '
           'max(gap,1), so the bound is the observation'
           % (dropped, gap, problems, STEP, control_problems))


# ---------------------------------------------------------------- F11
def f11_sequence_is_log_index():
    """Recorder numbers samples by log index, so schema's contiguity check
    can never fire on a lossy log."""
    import recorder
    recs = [{'sim_ns': T0 + STEP * i, 'monotonic_ns': T0 + STEP * i,
             'objects': {'target_box_a': {'pose': [0.22, 0.0, REST, 0, 0, 0, 1]},
                         'target_box_b': {'pose': [0.20, -0.18, REST, 0, 0, 0, 1]}}}
            for i in range(80) if i % 2 == 0]        # half the steps lost
    samples, dropped, _gap = recorder.trajectory_from_physics(recs, 'target_box_a')
    contiguous = all(samples[i + 1][0] == samples[i][0] + 1
                     for i in range(len(samples) - 1))
    record('F11',
           'a physics log missing every other step must not produce a '
           'contiguous sequence',
           not contiguous,
           '40 of 80 steps present, dropped_samples=%d, emitted sequence=%r..%r '
           'contiguous=%r | recorder.py:84 uses the enumerate() index'
           % (dropped, samples[0][0], samples[-1][0], contiguous))


# ---------------------------------------------------------------- F12
def f12_dropped_samples_unread():
    """dropped_samples is validated but no gate reads it."""
    b = fixtures.base_bundle()
    b['objects']['block-1']['dropped_samples'] = 937
    r = verify.verify(b, fixtures.terminal_verdict(True), fixtures.limits())
    record('F12',
           'a bundle that dropped 937 samples must not pass as complete',
           not r['passed'],
           'dropped_samples=937 -> passed=%r problems=%r | the field is '
           'range-checked (schema.py:131) and never consumed'
           % (r['passed'], schema.validate(b)))


# ---------------------------------------------------------------- F13
def f13_limits_divergence():
    """The unit tests exercise 0.005; evaluate.py passes 0.020."""
    out = []
    for lift in (0.004, 0.008, 0.0095, 0.012):
        b = bundle_with(REST, lambda i, L=lift: REST + L * math.sin(
            math.pi * i / (N - 1.0)))
        v_fix = verify.verify(b, fixtures.terminal_verdict(True), fixtures.limits())
        v_eval = verify.verify(b, fixtures.terminal_verdict(True), EVAL_LIMITS)
        out.append('lift=%.1fmm fixtures=%r evaluate=%r'
                   % (lift * 1000, v_fix['passed'], v_eval['passed']))
    diverged = any('fixtures=False' in s and 'evaluate=True' in s for s in out)
    record('F13',
           'the verifier tests must exercise the limit the production caller '
           'actually passes',
           not diverged,
           '%s | fixtures.limits() uses 0.005 (fixtures.py:189); '
           'evaluate.py:327 passes 0.020' % ' ; '.join(out))


# ---------------------------------------------------------------- F14
def f14_overshoot_indistinguishable():
    """Overshoot and undershoot produce the same failed_clauses string."""
    rows = {}
    for label, dx in (('undershoot_4mm', -0.0001),
                      ('overshoot_157mm', -0.004026)):
        b = bundle_with(REST, lambda i: REST, dx=dx)
        v = ev.evaluate(spec(SPEC2000),
                        state_with(b, REST, x=0.22 + dx * 39))
        clause = [c for c in v['clauses'] if c['clause'].startswith('push:')][0]
        rows[label] = (v['failed_clauses'], clause['evidence']['displacement_m'],
                       clause['evidence']['inside_zone'])
    same = rows['undershoot_4mm'][0] == rows['overshoot_157mm'][0]
    record('F14',
           'an overshoot and an undershoot must be distinguishable from the '
           'verdict alone',
           not same,
           'undershoot failed_clauses=%r (d=%.4f, in_zone=%r) ; overshoot '
           'failed_clauses=%r (d=%.4f, in_zone=%r) | evaluate.py:241 collapses '
           'both into one boolean; the numbers survive only in clause evidence'
           % (rows['undershoot_4mm'] + rows['overshoot_157mm']))


# ---------------------------------------------------------------- F15
def f15_no_attachment_inconsistent():
    """events is not cross-checked against attached_during_window."""
    b = fixtures.base_bundle()
    b['attachment'] = {'events': 0, 'attached_during_window': False}
    b['attachment']['events'] = 5          # 5 attachment events, none during window
    r = verify.verify(b, fixtures.terminal_verdict(True), fixtures.limits())
    g = [x for x in r['gates'] if x['gate'] == 'no_attachment'][0]
    record('F15',
           'an attachment count that contradicts attached_during_window must '
           'not pass silently',
           not g['ok'],
           'events=5 with attached_during_window=False -> gate ok=%r | '
           'verify.py:358 only range-checks events' % (g['ok'],))


# ---------------------------------------------------------------- F16
def f16_bridge_drops_evidence():
    """The production observation bridge strips the evidence and trajectory."""
    import observe_from_run as ofr
    obs = {'objects': {'target_box_a': [0.12, 0.0, REST, 0.0]},
           'move_sequence': [], 'agent_claimed_success': True,
           'agent_claim_source': 'measured', 'visits': {},
           'trajectory': {'target_box_a': {'max_z_m': REST}},
           'evidence': bundle_with(REST, lambda i: REST)}
    stripped = ofr.strip_diagnostics(obs)
    record('F16',
           'the bridge that builds a production observation must carry the '
           'evidence bundle through to evaluate.py',
           'evidence' in stripped and 'trajectory' in stripped,
           'strip_diagnostics keep-set -> %r | evidence present=%r '
           'trajectory present=%r | observe_from_run.py:148-149'
           % (sorted(stripped), 'evidence' in stripped,
              'trajectory' in stripped))


# ---------------------------------------------------------------- F17
def f17_frozen_numbers():
    """The frozen thresholds are still the frozen thresholds."""
    s = spec(SPEC2000)
    push = s['expected_goal']['push']['target_box_a']
    ok = (push['min_displacement_m'] == 0.030
          and push['max_displacement_m'] == 0.150
          and push['max_vertical_m'] == 0.020
          and push['min_direction_cosine'] == 0.9
          and s['zones'][0]['radius'] == 0.06
          and ev.EVALUATOR_VERSION == '0.5.0'
          and verify.VERIFIER_VERSION == '1.0.0')
    record('F17',
           'frozen numbers unchanged: 0.03 / 0.15 / 0.02 / 0.9 / zone 0.06',
           ok,
           'min_disp=%r max_disp=%r max_vert=%r cos=%r zone_radius=%r '
           'evaluator=%r verifier=%r'
           % (push['min_displacement_m'], push['max_displacement_m'],
              push['max_vertical_m'], push['min_direction_cosine'],
              s['zones'][0]['radius'], ev.EVALUATOR_VERSION,
              verify.VERIFIER_VERSION))


# ---------------------------------------------------------------- F18
def f18_gripper_limit_naming():
    """F18 (LOW): the aperture bound is NAMED _rad but carries METRES.

    Verified against the URDF: gripper_left_joint and gripper_right_joint are
    PRISMATIC (axis 0 1 0 / 0 -1 0, limit lower=-0.011 upper=0.02), so a joint
    position is a linear displacement in metres. The value 0.002 is therefore
    genuinely 2 mm and there is NO mm-to-radian error - an earlier version of
    this finding claimed one and was retracted (see FINDING_F18_GRIPPER_
    CORRECTION.md).

    What remains is the naming: the field asserts radians while carrying
    metres, and verify.py reports it back as limit_rad. That mislabels the
    quantity for every future reader. It cannot admit or reject a run by
    itself, hence LOW.
    """
    src_v = open(os.path.join(WT, 'benchmark', 'evidence', 'verify.py'),
                 encoding='utf-8').read()
    misnamed = 'limit_rad' in src_v
    record('F18',
           'the aperture-change bound must not assert a unit the quantity does '
           'not have (the gripper joints are prismatic: metres, not radians)',
           not misnamed,
           'verify.py reports limit_rad=%r while the value is metres; '
           'fixtures.py:192 names the field max_aperture_change_rad. URDF: '
           'gripper_left_joint type="prismatic", limit -0.011..0.02 => 0.002 m '
           'IS 2 mm. NAMING ONLY, LOW severity. The earlier mm-to-rad claim is '
           'RETRACTED.' % misnamed)


FINDINGS = {
    'F1': f1_carry_as_push, 'F1b': f1b_carry_honest_control,
    'F2': f2_rest_height_unbound, 'F3': f3_max_z_trusted,
    'F4': f4_digest_never_recomputed, 'F5': f5_manifest_completeness_unused,
    'F6': f6_evidence_replay, 'F7': f7_window_decorative,
    'F8': f8_gripper_single_sample, 'F9': f9_pusher_links_self_declared,
    'F10': f10_max_gap_tautology, 'F11': f11_sequence_is_log_index,
    'F12': f12_dropped_samples_unread, 'F13': f13_limits_divergence,
    'F14': f14_overshoot_indistinguishable, 'F15': f15_no_attachment_inconsistent,
    'F16': f16_bridge_drops_evidence, 'F17': f17_frozen_numbers, 'F18': f18_gripper_limit_naming,
}


def main(argv):
    wanted = [a for a in argv[1:] if a in FINDINGS] or list(FINDINGS)
    print('=' * 74)
    print('9-GATE T08 VERIFIER AUDIT - reproducers (%d findings)' % len(wanted))
    print('repo: %s' % WT)
    print('verify.py v%s / evaluate.py v%s / schema %s'
          % (verify.VERIFIER_VERSION, ev.EVALUATOR_VERSION, schema.SCHEMA_VERSION))
    print('=' * 74)
    for fid in wanted:
        print()
        print('--- %s ---' % fid)
        FINDINGS[fid]()
    print()
    print('=' * 74)
    findings = [r for r in RESULTS if not r[2]]
    print('SUMMARY: %d checks, %d properties HOLD, %d FINDINGS'
          % (len(RESULTS), len(RESULTS) - len(findings), len(findings)))
    for fid, claim, _holds, _detail in findings:
        print('  FINDING %-4s %s' % (fid, claim))
    print('=' * 74)
    return 1 if findings else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))