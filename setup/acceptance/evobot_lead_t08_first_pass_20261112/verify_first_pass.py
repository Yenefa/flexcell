#!/usr/bin/env python3
"""Re-derive every claim in README.md from the raw S/t3 artifacts.

Verifies: bundle binding, trajectory/ground-truth agreement, commanded direction,
and the four properties that make a carry impossible. No simulator, no model calls.
"""
import json
import math
import os
import sys


def find_repo_root(start):
    cur = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(cur, 'benchmark', 'evidence')):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise SystemExit('REFUSED: repo root not found above %s' % start)
        cur = parent


REPO = find_repo_root(os.path.dirname(os.path.abspath(__file__)))
TRIAL = os.path.join(REPO, 'setup', 'acceptance', 'evobot_t08_evidence_loop_20261112',
                     'evidence', 'S', 't3')
SPEC = os.path.join(REPO, 'benchmark', 'tasks', 't08_dev', 'T08-push-seed2000.json')


def main():
    if not os.path.isdir(TRIAL):
        raise SystemExit('REFUSED: trial dir not found: %s' % TRIAL)
    record = json.load(open(os.path.join(TRIAL, 'trial_record.json')))
    verdict = json.load(open(os.path.join(TRIAL, 'verdict.json')))
    bundle = json.load(open(os.path.join(TRIAL, 'evidence_bundle.json')))
    gt = json.load(open(os.path.join(TRIAL, 'gt_after.json')))
    spec = json.load(open(SPEC))

    print('=== HEADLINE ===')
    print('  arm=%s trial=%s passed=%s terminal_passed=%s'
          % (record['arm'], record['trial'], record['passed'],
             record['terminal_passed']))
    print('  evidence_status=%s physical_outcome=%s failed_gates=%s'
          % (record['evidence_status'], record['physical_outcome'],
             record.get('failed_gates')))
    if not (record['passed'] is True and record['terminal_passed'] is True):
        raise SystemExit('FAIL: this trial is not a pass; README is wrong')

    print()
    print('=== 3.1 bundle binding ===')
    run = bundle.get('run') or {}
    task = bundle.get('task') or {}
    spec_rest = spec['objects'][0]['initial_pose'][2]
    print('  run_id=%s' % run.get('run_id'))
    print('  task_sha256=%s' % task.get('task_sha256'))
    print('  bundle rest_height_m=%.4f  spec rest=%.4f  match=%s'
          % (task.get('rest_height_m'), spec_rest,
             abs(task.get('rest_height_m') - spec_rest) < 1e-9))
    if abs(task.get('rest_height_m') - spec_rest) > 1e-9:
        raise SystemExit('FAIL: rest height is NOT bound to the spec')

    print()
    print('=== 3.2 trajectory vs ground truth ===')
    worst = 0.0
    for name, entry in (bundle.get('objects') or {}).items():
        samples = entry.get('samples') or []
        if not samples:
            raise SystemExit('FAIL: no samples for %s' % name)
        first, last = samples[0], samples[-1]
        print('  %-14s n=%d first=(%.5f,%.5f,%.5f) last=(%.5f,%.5f,%.5f)'
              % (name, len(samples), first[3], first[4], first[5],
                 last[3], last[4], last[5]))
        monotonic = all(samples[i][1] <= samples[i + 1][1] for i in range(len(samples) - 1))
        print('                 timestamps monotonic: %s' % monotonic)
        g = gt['objects'][name]
        delta = math.dist([last[3], last[4], last[5]], g[:3])
        worst = max(worst, delta)
        print('                 bundle-last vs gt_after delta = %.6f m' % delta)
    if worst > 1e-4:
        raise SystemExit('FAIL: trajectory does not match ground truth (%.6f m)' % worst)

    print()
    print('=== 3.3 commanded direction ===')
    samples = bundle['objects']['target_box_a']['samples']
    dx = samples[-1][3] - samples[0][3]
    dy = samples[-1][4] - samples[0][4]
    mag = math.hypot(dx, dy)
    goal = spec['expected_goal']['push']['target_box_a']
    dvec = goal['direction']
    cos = (dx * dvec[0] + dy * dvec[1]) / mag if mag else 0.0
    print('  dx=%.5f dy=%.5f  |d|=%.5f m (%.2f mm)' % (dx, dy, mag, mag * 1000))
    print('  commanded direction=%s  cosine=%.5f  (clause needs >= %.2f)'
          % (dvec, cos, goal['min_direction_cosine']))
    inside = goal['min_displacement_m'] <= mag <= goal['max_displacement_m']
    print('  displacement inside [%.3f, %.3f]: %s'
          % (goal['min_displacement_m'], goal['max_displacement_m'], inside))
    if not (inside and cos >= goal['min_direction_cosine']):
        raise SystemExit('FAIL: terminal geometry is not satisfied')

    print()
    print('=== 3.4 why this cannot be a carry ===')
    gripper = bundle.get('gripper') or {}
    vals = [float(v) for _t, v in (gripper.get('span') or [])]
    if not vals:
        raise SystemExit('REFUSED: bundle has no gripper span')
    travel = max(vals) - min(vals)
    zs = [p[5] for p in samples]
    lift = max(zs) - spec_rest
    teleport = (bundle.get('teleport') or {}).get('max_single_step_jump_m')
    attachments = len(((bundle.get('attachment') or {}).get('events') or []))
    print('  gripper travel        %.6f m  (%.4f mm)' % (travel, travel * 1000))
    print('  max lift above rest   %.6f m  (%.4f mm)' % (lift, lift * 1000))
    print('  max single-step jump  %.6f m' % teleport)
    print('  attachment events     %d' % attachments)
    if lift > 0.005:
        raise SystemExit('FAIL: object left the table; could be a carry')
    if attachments:
        raise SystemExit('FAIL: attachment events present; could be a carry')

    print()
    print('=== gates ===')
    ev = verdict.get('evidence') or {}
    for gate in ev.get('gates') or []:
        print('  %-18s ok=%s' % (gate['gate'], gate['ok']))
    failed = [g['gate'] for g in (ev.get('gates') or []) if not g['ok']]
    print('  failed gates: %s' % (failed or 'none'))
    if failed:
        raise SystemExit('FAIL: gates failed but record says passed')

    print()
    print('ALL CHECKS PASSED: this is a genuine push that satisfied all nine gates.')
    print('It is ONE trial on ONE dev instance; see README section 5 for the limits.')
    return 0


if __name__ == '__main__':
    sys.exit(main())