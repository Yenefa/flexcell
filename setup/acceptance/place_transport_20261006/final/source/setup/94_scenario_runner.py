#!/usr/bin/env python3
"""Scenario runner for the M2 benchmark cells (issue #7 remainder / §4.2).

Orchestrates episodes end-to-end WITHOUT hand-orchestration:
  per episode: admin reset -> arm /flexcell/inject (if any) -> run the demo
  (or task) via w1_client -> clear injection -> locate the episode record ->
  offline FSM policy-input replay -> summary row. Model replay is NOT_RUN
  until a pinned backend is supplied; model batches report RECORDED, not PASS.

Scenario suite (S6 cold-start needs the lifecycle CLI - new-machine flow;
S7 perturbation is separate issue #9):

  S1  canonical happy demo            inject: none            expect SUCCEEDED
  S2  injected failure first attempt  inject: <scenario>:once expect SUCCEEDED
  S3  injected PICK_B first attempt   inject: <scenario>@B:once expect SUCCEEDED
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
import os
import subprocess
import sys
import time

from flexcell_skills.contracts.benchmark_protocol import load_protocol, check_scenario_execution
from flexcell_skills.contracts.episode import replay_episode
from flexcell_skills.contracts.metrics import wilson
from flexcell_skills.contracts.routing_audit import audit_routing_episode
from flexcell_skills.decision_policy import FSMPolicy

ROS_LOG = os.path.expanduser('~/.ros/flexcell')
EPISODE_DIR = os.path.join(ROS_LOG, 'episodes')

PROTOCOL, PROTOCOL_SHA256 = load_protocol()
SCENARIOS = PROTOCOL['scenarios']
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def arm_inject(client, payload, expect=None):
    """Arm, or explicitly CLEAR, the failure injection - and SEAL the step.

    `None` means "leave the injection alone" (scenarios S1/S4/S7).  Any other
    string is published; the EMPTY string is the clear signal.  The previous
    `if payload:` guard made '' a no-op, so the post-episode clear never
    reached the client and an armed injection stayed live for every later
    episode (measured 2026-09-29: with S5 before S7, all 10 S7 episodes were
    pre-failed by the leftover `exhaust_demo_v1:always` injection).

    The client now waits for the matching lifecycle state and exits non-zero if
    it is not observed, so a request that never lands cannot silently run a
    cell under the wrong condition (measured: 1 S5 episode of 20 SUCCEEDED
    because its `always` injection never armed).  Returns (ok, detail).
    """
    if payload is None:
        return True, 'skipped'
    request_id = 'r%d' % (int(time.time() * 1000) % 100000000)
    want = expect or ('armed' if payload else 'cleared')
    cmd = ['python3', client, '--action', 'inject', '--inject', payload,
           '--inject-request-id', request_id,
           '--expect-inject-state', want]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return False, 'timeout arming %r' % (payload,)
    if proc.returncode != 0:
        tail = ((proc.stdout or '') + (proc.stderr or '')).strip().splitlines()
        return False, tail[-1] if tail else 'rc=%d' % proc.returncode
    return True, '%s sealed' % want


def run_episode(client, spec, ws, seed=None):
    """One episode: reset, perturb (S7), inject, run, clear.
    Returns (rc, output, extra) where extra carries the S7 schedule."""
    admin_env = dict(os.environ, FLEXCELL_WS=ws)
    extra = {}
    try:
        reset = subprocess.run(['python3', os.path.join(REPO, 'setup/flexcell_admin.py'), 'reset'],
                               capture_output=True, text=True, timeout=300,
                               env=admin_env)
        extra['reset_rc'] = reset.returncode
        extra['reset_output'] = reset.stdout + reset.stderr
        if reset.returncode != 0 or '"ok": true' not in reset.stdout.lower():
            extra['harness_error'] = 'reset failed rc=%d: %s' % (
                reset.returncode, (reset.stdout + reset.stderr)[-1500:])
            return 90, 'HARNESS_ERROR: reset failed', extra
    except subprocess.TimeoutExpired:
        extra['harness_error'] = 'reset timed out'
        return 90, 'HARNESS_ERROR: reset timed out', extra
    if spec.get('perturb') and seed is not None:
        p = subprocess.run(['python3', os.path.join(REPO, 'setup/96_s7_perturb.py'),
                            '--seed', str(seed), '--apply'],
                           capture_output=True, text=True, timeout=60,
                           env=admin_env)
        try:
            extra['perturb'] = json.loads(
                p.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            extra['perturb'] = None
        if p.returncode != 0 or not extra['perturb'] or not extra['perturb'].get('placements'):
            extra['harness_error'] = 'perturbation failed'
            return 90, 'HARNESS_ERROR: perturbation failed', extra
    # A clean starting injection state is required even for uninjected cells.
    clear_ok, clear_detail = arm_inject(client, '')
    if not clear_ok:
        extra['harness_error'] = 'pre-episode injection clear failed: ' + clear_detail
        return 90, 'HARNESS_ERROR: injection clear failed', extra
    arm_ok, arm_detail = arm_inject(client, spec.get('inject'))
    extra['inject_arm'] = arm_detail
    if not arm_ok:
        # fail-closed: a cell whose injection was not armed would run under the
        # wrong condition, so this episode is a HARNESS error, never a policy
        # outcome.  Leave nothing armed for the next episode.
        arm_inject(client, '')
        return 90, 'HARNESS_ERROR: injection not armed (%s)' % arm_detail, extra
    cmd = ['python3', client, '--action', spec['kind']]
    if spec['kind'] == 'demo':
        cmd += ['--scenario', spec['scenario']]
    else:
        cmd += ['--object', spec['object'],
                '--pose'] + [str(v) for v in spec['pose']]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=220)
    except subprocess.TimeoutExpired:
        extra['harness_error'] = 'task client timed out (cancel/cleanup required)'
        return 90, 'HARNESS_ERROR: task client timed out', extra
    finally:
        clear_ok, clear_detail = arm_inject(client, '')
        extra['inject_clear'] = clear_detail
        if not clear_ok:
            extra['harness_error'] = 'injection not cleared: %s' % clear_detail
    return proc.returncode, (proc.stdout or '') + (proc.stderr or ''), extra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--batch', nargs='*', default=['S1:2'],
                    help='SCENARIO:count pairs, e.g. S1:2 S2:1 S5:1')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--dry-run', action='store_true', help='print the interleaved plan without ROS actions')
    ap.add_argument('--seed', type=int, default=20260930)
    ap.add_argument('--stage', choices=('smoke', 'baseline'), default='smoke')
    ap.add_argument('--smoke-summary', help='passing same-protocol smoke required for baseline')
    ap.add_argument('--deployment', help='frozen hybrid deployment JSON; enforce per-decision provenance')
    ap.add_argument('--policy', choices=('fsm', 'jev', 'llm', 'hybrid'), default='fsm',
                    help='expected policy of the running fleet (model replay is reported NOT_RUN)')
    ap.add_argument('--ws', default=os.environ.get('FLEXCELL_WS',
                                                   '/home/ros/agentic_workcell_ws'))
    args = ap.parse_args()

    deployment = None
    if args.deployment:
        if args.policy != 'hybrid':
            ap.error('--deployment routing audit requires --policy hybrid')
        with open(args.deployment, encoding='utf-8') as stream:
            deployment = json.load(stream)
        if deployment.get('policy') != args.policy:
            ap.error('deployment policy mismatch')

    if args.list:
        for k, v in SCENARIOS.items():
            print('%s: %s' % (k, v))
        return 0

    client = os.path.join(REPO, 'src/flexcell/flexcell_skills/test/w1_client.py')
    plan = []
    for item in args.batch:
        sid, _, count = item.partition(':')
        if sid not in SCENARIOS:
            print('unknown scenario %r (have %s)' % (sid, sorted(SCENARIOS)))
            return 2
        n = int(count or 1)
        if n < 1:
            ap.error('counts must be positive')
        plan += [(sid, n)]
    if not plan:
        ap.error('batch must contain at least one cell')
    if not args.dry_run and args.policy == 'hybrid' and deployment is None:
        ap.error('hybrid execution requires --deployment for routing provenance')
    baseline_profile = None
    if not args.dry_run and args.stage == 'smoke' and any(n > 5 for _, n in plan):
        ap.error('smoke is capped at n=5 per cell; baseline requires a passing smoke summary')
    if not args.dry_run and args.stage == 'baseline':
        if not args.smoke_summary:
            ap.error('baseline is blocked until --smoke-summary is supplied')
        with open(args.smoke_summary) as stream:
            smoke = [json.loads(line) for line in stream if line.strip()]
        profiles = {r.get('runtime_fingerprint') for r in smoke
                    if r.get('policy') == args.policy and r.get('runtime_fingerprint')}
        if len(profiles) != 1:
            ap.error('baseline requires smoke from one fingerprinted runtime')
        baseline_profile = profiles.pop()
        if deployment and deployment.get('runtime_fingerprint') != baseline_profile:
            ap.error('deployment differs from the qualifying smoke runtime')
        for sid, _ in plan:
            valid = [r for r in smoke if r.get('scenario') == sid and
                     r.get('protocol_sha256') == PROTOCOL_SHA256 and
                     r.get('runtime_fingerprint') == baseline_profile and
                     r.get('policy') == args.policy and r.get('stage') == 'smoke' and
                     (not deployment or (r.get('routing_audit') or {}).get('ok') is True) and
                     r.get('scenario_exercised') and not r.get('harness_error') and
                     r.get('outcome') == r.get('expected') and
                     (r.get('replay_ok') is True if args.policy == 'fsm'
                      else r.get('model_decisions', 0) > 0)]
            if len(valid) < 5:
                ap.error('baseline blocked: %s has fewer than five passing same-policy smoke runs' % sid)
    schedule = [(sid, i + 1, n) for i in range(max(n for _, n in plan))
                for sid, n in plan if i < n]
    if args.dry_run:
        print(json.dumps({'protocol_version': 2, 'seed': args.seed, 'policy': args.policy,
                          'protocol_id': PROTOCOL['protocol_id'], 'protocol_sha256': PROTOCOL_SHA256,
                          'stage': args.stage, 'order': 'round_robin', 'schedule': schedule,
                          'n': dict(plan)}, indent=2))
        return 0

    policy = FSMPolicy()
    rows = []
    batch_fingerprint = None
    batch_id = 'batch_%s' % time.strftime('%Y%m%d_%H%M%S')
    summary_path = os.path.join(EPISODE_DIR, '%s.jsonl' % batch_id)
    os.makedirs(EPISODE_DIR, exist_ok=True)
    print('scenario runner: %s' % dict(
        (k, v) for k, v in plan))
    for sid, run, count in schedule:
        spec = SCENARIOS[sid]
        i = run - 1
        print('  %s run %d/%d' % (sid, i + 1, count))
        before = set(glob.glob(os.path.join(EPISODE_DIR, '*.json')))
        rc, out, extra = run_episode(client, spec, args.ws,
                                     seed=args.seed + len(rows))
        harness_error = extra.get('harness_error')
        if rc == 90 and not harness_error:
            harness_error = extra.get('inject_arm')
        outcome = ('HARNESS_ERROR' if rc == 90 else
                   'SUCCEEDED' if '"outcome": "OUTCOME_SUCCEEDED"' in out
                   else 'CANCELED' if 'OUTCOME_CANCELED' in out
                   else 'FAILED')
        result = None
        if 'RESULT ' in out:
            try:
                result, _ = json.JSONDecoder().raw_decode(out.split('RESULT ', 1)[1])
            except ValueError:
                pass
        fresh = set(glob.glob(os.path.join(EPISODE_DIR, '*.json'))) - before
        matches = []
        for path in fresh:
            with open(path) as fh:
                record = json.load(fh)
            if result and record.get('final_state', {}).get('evidence_id') == result.get('evidence_id'):
                matches.append(path)
        ep_path = matches[0] if len(matches) == 1 else None
        if rc != 90 and (not result or ep_path is None):
            harness_error = 'missing or ambiguous episode for this result'
        replay_ok, replay_n = None, 0
        replay_status = 'NOT_RUN'
        scenario_exercised, scenario_detail = False, 'no episode'
        model_decisions = 0
        routing_audit = None
        if ep_path:
            try:
                with open(ep_path) as fh:
                    record = json.load(fh)
                recorded_protocol = record.get('benchmark_protocol') or {}
                if recorded_protocol.get('sha256') != PROTOCOL_SHA256:
                    harness_error = 'executor protocol does not match runner'
                if baseline_profile and record.get('runtime_fingerprint') != baseline_profile:
                    harness_error = 'runtime changed since the qualifying smoke'
                if batch_fingerprint is None:
                    batch_fingerprint = record.get('runtime_fingerprint')
                if not batch_fingerprint or record.get('runtime_fingerprint') != batch_fingerprint:
                    harness_error = 'missing or mixed runtime fingerprints within batch'
                if deployment:
                    routing_audit = audit_routing_episode(record, deployment)
                    if not routing_audit['ok']:
                        harness_error = 'routing provenance failed: ' + '; '.join(routing_audit['errors'])
                scenario_exercised, scenario_detail = check_scenario_execution(spec, record)
                model_decisions = sum(((step.get('policy_output') or {}).get('policy_trace') or {}).get('source') in ('jev', 'llm') for step in record.get('steps', []))
                recorded_policy = record.get('policy', {}).get('name')
                if recorded_policy != args.policy:
                    harness_error = 'policy mismatch: expected %s, got %s' % (args.policy, recorded_policy)
                elif args.policy == 'fsm':
                    results = replay_episode(record, policy)
                    replay_n = len(results)
                    replay_ok = bool(results) and all(r['ok'] for r in results)
                    replay_status = 'PASS' if replay_ok else 'FAIL'
                else:
                    replay_status = 'NOT_RUN (requires pinned model backend replay)'
            except (ValueError, KeyError, OSError):
                replay_ok = False
                replay_status = 'FAIL'
        row = {
            'scenario': sid, 'run': i + 1, 'rc': rc, 'outcome': outcome,
            'expected': spec['expect'], 'episode': ep_path,
            'replay_ok': replay_ok, 'replay_steps': replay_n,
            'perturb': extra.get('perturb'),
            'inject_arm': extra.get('inject_arm'),
            'inject_clear': extra.get('inject_clear'),
            'harness_error': harness_error,
            'ts': time.time(),
            'protocol_version': 2, 'seed': args.seed + len(rows),
            'policy': args.policy, 'replay_status': replay_status,
            'protocol_id': PROTOCOL['protocol_id'], 'protocol_sha256': PROTOCOL_SHA256,
            'stage': args.stage, 'scenario_exercised': scenario_exercised,
            'runtime_fingerprint': record.get('runtime_fingerprint') if ep_path else None,
            'scenario_detail': scenario_detail, 'model_decisions': model_decisions,
            'routing_audit': routing_audit,
            'reset_rc': extra.get('reset_rc'), 'reset_output': extra.get('reset_output'),
            'client_output': out,
        }
        if harness_error:
            row['outcome'] = 'HARNESS_ERROR'
        rows.append(row)
        # Preserve completed evidence even if a later ROS action blocks or
        # the user interrupts a long batch.
        with open(summary_path, 'a') as fh:
            fh.write(json.dumps(row, sort_keys=True) + '\n')
        print('    outcome=%s expected=%s replay=%s (%d steps) arm=%s clear=%s'
              % (outcome, spec['expect'], replay_ok, replay_n,
                 extra.get('inject_arm'), extra.get('inject_clear')))
        if harness_error:
            print('    stopping batch: ' + harness_error)
            break

    print('\n=== per-scenario results (metric #1, Wilson 95%% CI) ===')
    bad = 0
    for sid in dict(plan):
        sel = [r for r in rows if r['scenario'] == sid]
        # a HARNESS_ERROR episode is not a policy outcome: it is excluded from
        # the success denominator, but it still fails the batch loudly.
        graded = [r for r in sel if r['outcome'] != 'HARNESS_ERROR']
        harness = len(sel) - len(graded)
        succ = sum(1 for r in graded if r['outcome'] == 'SUCCEEDED')
        lo, hi = wilson(succ, len(graded))
        print('  %s: %d/%d SUCCEEDED, CI95=[%.2f, %.2f], replay_ok=%s%s'
              % (sid, succ, len(graded), lo, hi,
                 all(r['replay_ok'] for r in graded),
                 (', %d HARNESS_ERROR excluded' % harness) if harness else ''))
        if len(sel) != dict(plan)[sid]:
            bad += 1
        for r in sel:
            if (r['outcome'] == 'HARNESS_ERROR'
                    or r['outcome'] != r['expected']
                    or not r['scenario_exercised']
                    or (args.policy != 'fsm' and r['model_decisions'] == 0)
                    or (args.policy == 'fsm' and r['replay_ok'] is not True)):
                bad += 1
    print('batch summary: %s' % summary_path)
    success_status = 'PASS' if args.policy == 'fsm' else 'RECORDED (model replay NOT_RUN)'
    print('SCENARIO RUNNER: %s' % (success_status if bad == 0 else 'FAIL (%d)' % bad))
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
