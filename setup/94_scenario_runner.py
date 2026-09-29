#!/usr/bin/env python3
"""Scenario runner for the M2 benchmark cells (issue #7 remainder / §4.2).

Orchestrates episodes end-to-end WITHOUT hand-orchestration:
  per episode: admin reset -> arm /flexcell/inject (if any) -> run the demo
  (or task) via w1_client -> clear injection -> locate the episode record ->
  offline policy-input replay (must reproduce every decision) -> summary row.

Scenario suite (S6 cold-start needs the lifecycle CLI - new-machine flow;
S7 perturbation is separate issue #9):

  S1  canonical happy demo            inject: none            expect SUCCEEDED
  S2  injected failure first attempt  inject: <scenario>:once expect SUCCEEDED
  S4  unreachable place target        inject: none            expect FAILED (typed)
  S5  retry exhaustion                inject: <scenario>:always expect FAILED (typed)

Usage (ROS env sourced, stack running):
  python3 setup/94_scenario_runner.py --batch S1:2 S2:1 S5:1
  python3 setup/94_scenario_runner.py --list

Writes a batch summary to ~/.ros/flexcell/episodes/batch_<ts>.jsonl (one row
per episode: outcome, expected, replay_ok, safety metrics) and prints the
per-scenario success table with Wilson 95% CIs.  Exit 0 iff every episode
replayed cleanly AND every outcome matched its expectation.
"""
import argparse
import glob
import json
import math
import os
import subprocess
import sys
import time

from flexcell_skills.contracts.episode import replay_episode
from flexcell_skills.contracts.metrics import wilson
from flexcell_skills.decision_policy import FSMPolicy

ROS_LOG = os.path.expanduser('~/.ros/flexcell')
EPISODE_DIR = os.path.join(ROS_LOG, 'episodes')

SCENARIOS = {
    'S1': {'kind': 'demo', 'scenario': 'week1_demo_v1', 'inject': None,
           'expect': 'SUCCEEDED'},
    'S2': {'kind': 'demo', 'scenario': 'recovery_demo_v1',
           'inject': 'recovery_demo_v1:once', 'expect': 'SUCCEEDED'},
    'S4': {'kind': 'task', 'object': 'target_box_a',
           'pose': [0.42, 0.0, 0.0175], 'inject': None, 'expect': 'FAILED'},
    'S5': {'kind': 'demo', 'scenario': 'exhaust_demo_v1',
           'inject': 'exhaust_demo_v1:always', 'expect': 'FAILED'},
    'S7': {'kind': 'demo', 'scenario': 's7_perturb_v1', 'inject': None,
           'perturb': True, 'expect': 'SUCCEEDED'},
}


def newest_episode():
    files = sorted(glob.glob(os.path.join(EPISODE_DIR, '*.json')),
                   key=os.path.getmtime)
    return files[-1] if files else None


def arm_inject(client, payload):
    """Arm, or explicitly CLEAR, the failure injection.

    `None` means "leave the injection alone" (scenarios S1/S4/S7); any string
    is published, and the EMPTY string is the clear signal the pick server
    understands.  The previous `if payload:` guard made '' a no-op, so the
    runner's post-episode "always clear" never reached the client and an armed
    `once`/`always` injection stayed live for every later episode of the batch
    (measured 2026-09-29: with S5 before S7, all 10 S7 episodes were pre-failed
    by the leftover `exhaust_demo_v1:always` injection -> S7 0/10).  Cells
    ordered after an injecting scenario were therefore invalid.
    """
    if payload is None:
        return
    subprocess.run(['python3', client, '--action', 'inject',
                    '--inject', payload], capture_output=True, timeout=60)


def run_episode(client, spec, ws, seed=None):
    """One episode: reset, perturb (S7), inject, run, clear.
    Returns (rc, output, extra) where extra carries the S7 schedule."""
    admin_env = dict(os.environ, FLEXCELL_WS=ws)
    subprocess.run(['python3', 'setup/flexcell_admin.py', 'reset'],
                   capture_output=True, timeout=300, env=admin_env)
    extra = {}
    if spec.get('perturb') and seed is not None:
        p = subprocess.run(['python3', 'setup/96_s7_perturb.py',
                            '--seed', str(seed), '--apply'],
                           capture_output=True, text=True, timeout=60,
                           env=admin_env)
        try:
            extra['perturb'] = json.loads(
                p.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            extra['perturb'] = None
    arm_inject(client, spec.get('inject'))
    cmd = ['python3', client, '--action', spec['kind']]
    if spec['kind'] == 'demo':
        cmd += ['--scenario', spec['scenario']]
    else:
        cmd += ['--object', spec['object'],
                '--pose'] + [str(v) for v in spec['pose']]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=220)
    arm_inject(client, '')   # always clear
    return proc.returncode, (proc.stdout or '') + (proc.stderr or ''), extra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--batch', nargs='*', default=['S1:2'],
                    help='SCENARIO:count pairs, e.g. S1:2 S2:1 S5:1')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--ws', default=os.environ.get('FLEXCELL_WS',
                                                   os.getcwd()))
    args = ap.parse_args()

    if args.list:
        for k, v in SCENARIOS.items():
            print('%s: %s' % (k, v))
        return 0

    client = os.path.join(args.ws, 'src/flexcell/flexcell_skills/test/w1_client.py')
    plan = []
    for item in args.batch:
        sid, _, count = item.partition(':')
        if sid not in SCENARIOS:
            print('unknown scenario %r (have %s)' % (sid, sorted(SCENARIOS)))
            return 2
        plan += [(sid, int(count or 1))]

    policy = FSMPolicy()
    rows = []
    batch_id = 'batch_%s' % time.strftime('%Y%m%d_%H%M%S')
    print('scenario runner: %s' % dict(
        (k, v) for k, v in plan))
    for sid, count in plan:
        spec = SCENARIOS[sid]
        for i in range(count):
            print('  %s run %d/%d' % (sid, i + 1, count))
            rc, out, extra = run_episode(client, spec, args.ws,
                                         seed=1000 + len(rows))
            outcome = ('SUCCEEDED' if '"outcome": "OUTCOME_SUCCEEDED"' in out
                       else 'CANCELED' if 'OUTCOME_CANCELED' in out
                       else 'FAILED')
            ep_path = newest_episode()
            replay_ok, replay_n = None, 0
            if ep_path:
                try:
                    with open(ep_path) as fh:
                        record = json.load(fh)
                    results = replay_episode(record, policy)
                    replay_n = len(results)
                    replay_ok = all(r['ok'] for r in results)
                except (ValueError, KeyError, OSError):
                    replay_ok = False
            row = {
                'scenario': sid, 'run': i + 1, 'rc': rc, 'outcome': outcome,
                'expected': spec['expect'], 'episode': ep_path,
                'replay_ok': replay_ok, 'replay_steps': replay_n,
                'perturb': extra.get('perturb'),
                'ts': time.time(),
            }
            rows.append(row)
            print('    outcome=%s expected=%s replay=%s (%d steps)'
                  % (outcome, spec['expect'], replay_ok, replay_n))

    summary_path = os.path.join(EPISODE_DIR, '%s.jsonl' % batch_id)
    os.makedirs(EPISODE_DIR, exist_ok=True)
    with open(summary_path, 'w') as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + '\n')

    print('\n=== per-scenario results (metric #1, Wilson 95%% CI) ===')
    bad = 0
    for sid in dict(plan):
        sel = [r for r in rows if r['scenario'] == sid]
        succ = sum(1 for r in sel if r['outcome'] == 'SUCCEEDED')
        lo, hi = wilson(succ, len(sel))
        expect_ok = SCENARIOS[sid]['expect'] == 'SUCCEEDED'
        print('  %s: %d/%d SUCCEEDED, CI95=[%.2f, %.2f], replay_ok=%s'
              % (sid, succ, len(sel), lo, hi,
                 all(r['replay_ok'] for r in sel)))
        for r in sel:
            if r['outcome'] != r['expected'] or r['replay_ok'] is not True:
                bad += 1
    print('batch summary: %s' % summary_path)
    print('SCENARIO RUNNER: %s' % ('PASS' if bad == 0 else 'FAIL (%d)' % bad))
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
