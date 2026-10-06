#!/usr/bin/env python3
"""Recheck native/composite receipts offline; never pool them as independent trials."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import t3_swap_pilot as pilot
from adjudicate_t1 import latency

sys.path.insert(0, str(pilot.REPO / 'src/flexcell/flexcell_skills'))
from flexcell_skills.contracts.episode import replay_episode
from flexcell_skills.contracts.routing_audit import audit_routing_episode
from flexcell_skills.decision_policy import FSMPolicy


def report(root):
    root = root.resolve(strict=True)
    rows = pilot.COST.read_ledger(root / 'cost.jsonl')
    cost = pilot.COST.summarize(rows)
    manifest = pilot.load(root / 'plan/task_manifest.json')
    pilot.COST.require(pilot.base.sha(Path(pilot.__file__)) == manifest['shared_executor_sha256'], 'executor differs from registered source')
    native_trials = [r['payload'] for r in rows[1:] if r['payload']['kind'] == 'trial'
                     and r['payload']['case_id'] != 'T3-orchestration-check']
    observed_ids, arms = [], []
    for arm in ('fsm', 'hybrid'):
        directory = root / arm
        status = pilot.load(directory / 'status.json')
        deployment = pilot.load(directory / 'deployment.json')
        parent = pilot.load(directory / 'composite/summary.json')
        pilot.COST.require(deployment['runtime_fingerprint'] == manifest['expected_fingerprints'][arm], 'deployment identity changed')
        native, purpose_episodes, purpose_audits, controllers = [], {'adaptation': [], 'regression': []}, {'adaptation': [], 'regression': []}, []
        for p in sorted(directory.glob('**/summary.json')):
            if p.parent.name == 'composite':
                continue
            summary = pilot.load(p)
            if not (p.parent / 'episode.json').exists():
                native.append(dict(stage_id=summary['stage_id'], outcome=summary['outcome'], run_id=None))
                continue
            episode, client = pilot.load(p.parent / 'episode.json'), pilot.load(p.parent / 'client.json')
            result = pilot.base.result_from_output(client['stdout'])
            pilot.COST.require(result == summary['reported_client_result'] and client['return_code'] == summary['command_rc'], 'client binding mismatch')
            pilot.COST.require(episode['runtime_fingerprint'] == deployment['runtime_fingerprint'] and episode['run_id'] == summary['run_id'], 'native identity mismatch')
            if arm == 'hybrid':
                audit = audit_routing_episode(episode, deployment)
                pilot.COST.require(audit['ok'], 'hybrid routing audit failed')
            else:
                replay = replay_episode(episode, FSMPolicy())
                audit = dict(replay_status='PASS' if replay and all(r['ok'] for r in replay) else 'FAIL', replayed_steps=len(replay))
                pilot.COST.require(audit['replay_status'] == 'PASS', 'FSM replay failed')
            pilot.COST.require(audit == summary['audit'], 'recorded routing audit mismatch')
            passed = pilot.single_pass(episode, result, client['return_code'], summary['target']) if summary['target'] else pilot.base.success_predicate(episode, result, client['return_code'])
            expected = 'HARNESS_ERROR' if summary['harness_error'] else 'SUCCEEDED' if passed else 'FAILED'
            pilot.COST.require(summary['outcome'] == expected, 'native score differs from raw task evidence')
            event = next((e for e in native_trials if e['trial_id'] == episode['run_id']), None)
            pilot.COST.require(event is not None and event['evidence'] == [pilot.COST.pin(p)] and event['reported_outcome'] == summary['outcome'], 'ledger/native receipt binding mismatch')
            observed_ids.append(episode['run_id'])
            native.append(dict(stage_id=summary['stage_id'], run_id=episode['run_id'], outcome=summary['outcome']))
            purpose_episodes[summary['purpose']].append(episode)
            purpose_audits[summary['purpose']].append(audit)
            for raw in (p.parent / 'raw').glob('*transport.jsonl'):
                controllers.extend(pilot.COST.decode(line) for line in raw.read_text().splitlines() if line.strip())
        # Bind the parent's claims to the native task receipts, not just copies of their labels.
        for component in parent['components']:
            original = pilot.load(directory / 'composite' / component['stage_id'] / 'summary.json')
            pilot.COST.require(component == original, 'composite/native receipt mismatch')
        last = directory / 'composite/post-return-B.json'
        if last.exists():
            command = pilot.load(last)
            final = pilot.base.result_from_output(command['stdout'])
            pilot.COST.require(not pilot.base.signal_return_code(command['return_code']) and command['return_code'] is not None
                               and final == parent['final_observe'], 'final Observe not bound to actual command')
        passed = pilot.composite_pass(parent['components'], parent['final_observe']) and not parent['failure']
        pilot.COST.require((parent['outcome'] == 'SUCCEEDED') == bool(passed), 'composite predicate differs from recorded outcome')
        routing = {purpose: {field: sum(a.get(field, 0) for a in audits) for field in
                   ('fast_selected', 'slow_selected', 'fast_calls', 'fast_tokens', 'fsm_fallbacks')}
                   for purpose, audits in purpose_audits.items()} if arm == 'hybrid' else {'replay': 'PASS'}
        positions = pilot.observed_positions(parent['final_observe'])
        terminals = [r for r in controllers if r.get('event') == 'controller_goal_terminal']
        arms.append(dict(arm=arm, runtime_fingerprint=deployment['runtime_fingerprint'],
                         calibration_sha256=deployment['active_backends']['fast']['calibration_sha256'] if arm == 'hybrid' else None,
                         composite_attempts=1, composite_outcome=parent['outcome'], composite_id=parent['composite_id'],
                         source_regression_outcome=status['regression_outcome'], stop_reason=status['stop_reason'],
                         native_trials=native, native_episode_count=status['native_episode_count'],
                         final_joint_positions=positions, buffer_clear=pilot.vacant(positions, pilot.BUFFER), routing=routing,
                         decision_latency={purpose: latency(eps) for purpose, eps in purpose_episodes.items()},
                         controller_goal_terminals=len(terminals), controller_terminal_status_counts=dict(Counter(r['status'] for r in terminals)),
                         unknown_or_quarantined_transport_events=sum('quarantin' in str(r.get('event','')) or r.get('event') in ('goal_send_timeout','goal_response_unknown','goal_response_error') for r in controllers)))
    pilot.COST.require(len(observed_ids) == len(set(observed_ids)) and set(observed_ids) == {e['trial_id'] for e in native_trials if not e['trial_id'].endswith('-harness')}, 'duplicate/missing native episodes')
    status = pilot.load(root / 'hybrid/status.json')
    output = dict(record_kind='ACTUAL_COMPOSITE_TASK_PILOT_REPORT', protocol_id=manifest['protocol_id'],
                  model_scope='native task action routing; outer dependency sequence fixed for both arms', arms=arms,
                  native_episode_count=len(observed_ids), ledger=pilot.COST.pin(root / 'cost.jsonl'),
                  native_trial_cells=cost['trial_cells'], effort_minutes=cost['effort_minutes'], effort_status=cost['effort_status'],
                  shared_engineering=pilot.load(root / 'plan/shared_development.json'), api_usage=cost['api_usage'],
                  additional_paid_peak_uncached_upper_bound_cny=pilot.base.new_call_upper_bound(pilot.load(root / 'plan/registration_budget.json'), status['final_budget']) / 1e6,
                  invoice='UNKNOWN', gpu_energy_and_ownership_cost='UNKNOWN',
                  comparison='one composite attempt per arm, fixed order; no cost/reliability superiority claim',
                  AC90='NOT_RUN', qualification='FROZEN', n_ge_50='FROZEN', physical_safety_acceptance='NOT_RUN',
                  network_stability='NOT_ACCEPTED; DERP relay and earlier TCP failures retained',
                  receipt_pins=[pilot.COST.pin(root / a / 'composite/summary.json') for a in ('fsm','hybrid')])
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    output = report(args.root)
    pilot.base.write(args.out, output)
    print(json.dumps(dict(native_episodes=output['native_episode_count'],
                          arms=[dict(arm=a['arm'], composite=a['composite_outcome'], source=a['source_regression_outcome']) for a in output['arms']],
                          paid_upper_bound_cny=output['additional_paid_peak_uncached_upper_bound_cny'])))


if __name__ == '__main__':
    main()
