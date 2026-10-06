#!/usr/bin/env python3
"""Offline schema correction of an existing T1 pilot. Never sample or edit its ledger."""

import argparse
from collections import Counter, defaultdict
import copy
import json
import math
from pathlib import Path
import sys

import t1_pilot as pilot


COST = pilot.COST
REPO = pilot.REPO
sys.path.insert(0, str(REPO / 'src/flexcell/flexcell_skills'))
from flexcell_skills.contracts.routing_audit import audit_routing_episode
from flexcell_skills.contracts.episode import replay_episode
from flexcell_skills.decision_policy import FSMPolicy


def load(path):
    return COST.decode(Path(path).read_text())


def corrected_outcome(summary, episode, client):
    """Correct only the serialized task outcome; a harness failure stays a failure."""
    result = pilot.result_from_output(client['stdout'])
    COST.require(result == summary['reported_client_result'], 'client/summary result mismatch')
    COST.require(client['return_code'] == summary['command_rc'], 'client/summary return code mismatch')
    if summary['harness_error']:
        return 'HARNESS_ERROR'
    if pilot.signal_return_code(client['return_code']):
        return 'ABORTED_PROCESS'
    return 'SUCCEEDED' if pilot.success_predicate(episode, result, client['return_code']) else 'FAILED'


def latency(episodes):
    values = []
    missing = 0
    for episode in episodes:
        for step in episode['steps']:
            # The first observation is a bootstrap without a world snapshot.
            if step['policy_input'].get('world_state_canonical') is None:
                continue
            value = step.get('decide_latency_ms')
            if (step.get('decide_latency_clock') != 'perf_counter_ns'
                    or type(value) is not float or not math.isfinite(value) or value < 0):
                missing += 1
            else:
                values.append(value)
    if missing or not values:
        return dict(status='NOT_RUN', reason='missing/non-fractional perf_counter_ns measurements',
                    valid_samples=len(values), missing_samples=missing)
    ordered = sorted(values)
    def percentile(q):
        index = (len(ordered) - 1) * q
        lo, hi = math.floor(index), math.ceil(index)
        return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)
    return dict(status='MEASURED_DIAGNOSTIC', clock='perf_counter_ns', n=len(values),
                p50_ms=percentile(.5), p95_ms=percentile(.95),
                percentile_method='linear interpolation, index=(n-1)*q',
                scope='non-bootstrap complete policy.decide including escalation; not GPU-only latency')


def adjudicate(root, out):
    root = root.resolve(strict=True)
    rows = COST.read_ledger(root / 'cost.jsonl')
    original_cost = COST.summarize(rows)
    plan = rows[0]['payload']['plan']
    manifest = load(root / 'plan/task_manifest.json')
    initial = load(root / 'plan/initial_states.json')
    COST.require(plan['protocol_id'] == 'flexcell-transferbench-t1-pilot-v1', 'not a v1 T1 pilot')
    COST.require(not original_cost['open_effort_sessions'], 'pilot still has an open session')
    executed = root / 'source/t1_pilot_executed_v1.py'
    COST.require(pilot.sha(executed) == manifest['pilot_harness_sha256'], 'executed source not preserved')
    COST.require(pilot.sha(REPO / 'setup/125_transfer_cost.py') == manifest['ledger_cli_sha256'],
                 'cost instrument differs from registered version')
    trials = [row['payload'] for row in rows[1:] if row['payload']['kind'] == 'trial']
    trial_by_id = {row['trial_id']: row for row in trials}
    COST.require(len(trials) == len(trial_by_id) == 6, 'expected exactly six distinct pre-registered attempts')
    # Snapshot all original bytes before adding separate versioned outputs.
    inputs = {str(p.relative_to(root)): COST.pin(p) for p in sorted(root.rglob('*'))
              if p.is_file() and '__pycache__' not in p.parts and out not in p.parents}
    summaries, episodes, evidence = [], defaultdict(list), []
    for arm in ('fsm', 'hybrid'):
        status = load(root / arm / 'status.json')
        deployment = load(root / arm / 'deployment.json')
        COST.require(status['completed_attempts'] == 3 and status['stop_reason'] is None,
                     'incomplete/stopped pilot requires separate investigation')
        COST.require(deployment['runtime_fingerprint'] == manifest['expected_fingerprints'][arm],
                     'deployment identity mismatch')
        baseline = load(root / ('plan/baseline_' + arm + '.json'))
        COST.require(pilot.profile(deployment) == {k: v for k, v in baseline.items()
                     if k not in ('source_revision', 'coding_assistance', 'task_specific_source_changes_allowed',
                                  'runtime_fingerprint')}, 'baseline profile mismatch')
        for rel, expected in deployment['source_sha256'].items():
            COST.require(pilot.sha(REPO / rel) == expected, 'frozen skill source changed: ' + rel)
        for index in range(1, 4):
            attempt = root / arm / ('attempt%02d' % index)
            original = load(attempt / 'summary.json')
            episode, client = load(attempt / 'episode.json'), load(attempt / 'client.json')
            COST.require(type(episode.get('EpisodeSchemaVersion')) is int
                         and episode['EpisodeSchemaVersion'] == 1, 'unsupported episode schema')
            event = trial_by_id.get(episode['run_id'])
            COST.require(event is not None and event['arm'] == arm
                         and event['reported_outcome'] == original['outcome']
                         and event['evidence'] == [COST.pin(attempt / 'summary.json')], 'trial binding mismatch')
            case = manifest['source_case'] if index == 3 else manifest['target_case']
            layout = initial['source'] if index == 3 else initial['adaptation'][str(initial['seeds'][index-1])]
            COST.require(original['case_id'] == case and original['registered_layout'] == layout
                         and original['run_id'] == episode['run_id'], 'registered trial mismatch')
            states = [pilot.positions(COST.decode(step['policy_input']['world_state_canonical']))
                      for step in episode['steps'] if step['policy_input'].get('world_state_canonical')]
            COST.require(states and pilot.same_layout(states[0], layout), 'initial layout mismatch')
            COST.require(episode['runtime_fingerprint'] == event['runtime_fingerprint']
                         == deployment['runtime_fingerprint'], 'episode identity mismatch')
            if arm == 'hybrid':
                audit = audit_routing_episode(episode, deployment)
                COST.require(audit['ok'], 'hybrid provenance audit failed')
            else:
                replay = replay_episode(episode, FSMPolicy())
                audit = dict(replay_status='PASS' if replay and all(row['ok'] for row in replay) else 'FAIL',
                             replayed_steps=len(replay))
                COST.require(audit['replay_status'] == 'PASS', 'FSM replay failed')
            COST.require(audit == original['audit'], 'routing/replay evidence changed')
            corrected = corrected_outcome(original, episode, client)
            # This protocol corrects exactly one known representation defect.
            if corrected != original['outcome']:
                normalized = copy.deepcopy(episode)
                normalized['final_state']['outcome'] = 0
                COST.require(original['outcome'] == 'FAILED' and corrected == 'SUCCEEDED'
                             and episode['final_state']['outcome'] == '0'
                             and pilot.success_predicate(normalized, original['reported_client_result'],
                                                         original['command_rc']), 'change exceeds schema correction')
            support = [COST.pin(attempt / name) for name in ('summary.json', 'episode.json', 'client.json')]
            summary = dict(record_kind='POSTHOC_SCHEMA_CORRECTION', scorer_version=2,
                           original_reported_outcome=original['outcome'], outcome=corrected,
                           arm=arm, attempt=index, run_id=episode['run_id'], case_id=case,
                           purpose=original['purpose'], runtime_fingerprint=event['runtime_fingerprint'],
                           calibration_sha256=event['calibration_sha256'], return_code=client['return_code'],
                           unchanged_success_definition=load(root / 'plan/success_predicate.json')['definition'],
                           correction='canonical episode task outcome text "0" represents enum integer 0',
                           original_evidence=support, audit=audit, qualification='NOT_RUN')
            summaries.append(summary)
            episodes[(arm, original['purpose'], case)].append(episode)
    out.mkdir()  # refuse overwrite; original ledger and summaries remain intact
    for summary in summaries:
        path = out / ('%s-attempt%02d.json' % (summary['arm'], summary['attempt']))
        pilot.write(path, summary)
        evidence.append(COST.pin(path))
    for item in inputs.values():
        COST.require(COST.pin(item['path']) == item, 'original bytes changed during adjudication')
    correction = dict(record_kind='POSTHOC_SCHEMA_CORRECTION', scorer_version=2,
                      reason='v1 predicate expected int outcome, but EpisodeSchemaVersion 1 writes str(outcome)',
                      original_protocol_id=plan['protocol_id'], original_plan_sha256=COST.digest(plan),
                      parent_ledger=COST.pin(root / 'cost.jsonl'), original_inputs=inputs,
                      executed_source=COST.pin(executed), corrected_harness=COST.pin(Path(pilot.__file__)),
                      adjudicator=COST.pin(Path(__file__)), corrected_trial_receipts=evidence,
                      sampling='NO_NEW_EPISODES; same six run IDs; no replacement or pooled v1/v2 outcomes',
                      prospective_registration='original v1 plan retained; this correction is explicitly post hoc')
    pilot.write(out / 'correction_manifest.json', correction)
    cells = []
    for key, eps in episodes.items():
        arm, purpose, case = key
        selected = [s for s in summaries if (s['arm'], s['purpose'], s['case_id']) == key]
        counts = Counter(s['outcome'] for s in selected)
        n = counts['SUCCEEDED'] + counts['FAILED'] + counts['ABORTED_PROCESS']
        routing = {field: sum(s['audit'].get(field, 0) for s in selected) for field in
                   ('fast_selected', 'slow_selected', 'fast_calls', 'fast_tokens', 'fsm_fallbacks')}
        cells.append(dict(arm=arm, purpose=purpose, case_id=case,
                          runtime_fingerprint=selected[0]['runtime_fingerprint'],
                          calibration_sha256=selected[0]['calibration_sha256'], outcomes=dict(counts),
                          retained_attempts=len(selected), completed_denominator=n,
                          observed_success_rate=counts['SUCCEEDED']/n if n else None,
                          routing=routing if arm == 'hybrid' else {'replay_status': 'PASS'},
                          decision_latency=latency(eps), qualification='NOT_RUN'))
    report = dict(record_kind='POSTHOC_SCHEMA_CORRECTION', scorer_version=2,
                  original_protocol_id=plan['protocol_id'], correction_manifest=COST.pin(out / 'correction_manifest.json'),
                  parent_ledger=COST.pin(root / 'cost.jsonl'), trial_cells=cells,
                  original_v1_outcomes=dict(Counter(s['original_reported_outcome'] for s in summaries)),
                  cost_basis='unchanged verified parent ledger; corrected diagnostics are separate, no fabricated ledger chain',
                  effort_minutes=original_cost['effort_minutes'], effort_status=original_cost['effort_status'],
                  api_usage=original_cost['api_usage'],
                  task_specific_source_changes={arm: 0 for arm in plan['arms']},
                  shared_initial_configuration=dict(layouts=2, object_poses=4, numeric_components=12),
                  common_harness_authoring_cost='NOT_RUN',
                  additional_paid_peak_uncached_upper_bound_cny=pilot.new_call_upper_bound(
                      load(root / 'plan/registration_budget.json'), load(root / 'hybrid/status.json')['final_budget']) / 1e6,
                  actual_paid_invoice='UNKNOWN', gpu_energy_and_ownership_cost='UNKNOWN',
                  coding_assistant_tokens_and_fees='NOT_RUN; unavailable to experiment instrument',
                  AC90='NOT_RUN', qualification='FROZEN', physical_hardware='NOT_RUN',
                  comparison='fixed-order two-state diagnostic; no engineering-cost or reliability superiority claim')
    pilot.write(out / 'report.json', report)
    print(json.dumps(dict(out=str(out), corrected_trials=len(summaries),
                          outcomes=dict(Counter(s['outcome'] for s in summaries)),
                          paid_upper_bound_cny=report['additional_paid_peak_uncached_upper_bound_cny'])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    adjudicate(args.root, args.out.resolve())


if __name__ == '__main__':
    main()
