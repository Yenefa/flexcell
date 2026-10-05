#!/usr/bin/env python3
"""Freeze one S1 batch, retaining failures and original JSONL bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from flexcell_skills.contracts.episode import _sanitize
from flexcell_skills.contracts.metrics import latency_summary
from flexcell_skills.contracts.routing_audit import audit_routing_episode


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_lines(source, target, predicate):
    selected = []
    with source.open('rb') as stream:
        for line in stream:
            if line.strip() and predicate(json.loads(line)):
                selected.append(line)
    target.write_bytes(b''.join(selected))
    return [json.loads(line) for line in selected]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--batch', type=Path, required=True)
    ap.add_argument('--runtime', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--workspace', type=Path, default=Path('/home/ros/agentic_workcell_ws'))
    ap.add_argument('--log-root', type=Path, default=Path.home() / '.ros/flexcell')
    ap.add_argument('--offline-overlap', action='store_true')
    args = ap.parse_args()
    assert not args.out.exists(), 'Use a new stage directory; preserve previous evidence'
    deployment = json.loads((args.runtime / 'deployment.json').read_text())
    for rel, expected in {**deployment['source_sha256'], **deployment['harness_sha256']}.items():
        assert digest(args.workspace / rel) == expected, rel
    for rel, expected in deployment['installed_source_sha256'].items():
        installed = Path(deployment['install']) / 'flexcell_skills/lib/python3.12/site-packages/flexcell_skills'
        assert digest(installed / rel) == expected, rel
    profile = {k: v for k, v in deployment.items() if k not in ('runtime_fingerprint', 'head', 'install')}
    assert hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest() == deployment['runtime_fingerprint']
    batch = [json.loads(line) for line in args.batch.read_bytes().splitlines()]
    assert len(batch) == 5 and all(row['scenario'] == 'S1' for row in batch)
    assert all(row['runtime_fingerprint'] == deployment['runtime_fingerprint'] for row in batch)
    assert all(row['rc'] not in (-6, 134) for row in batch), 'SIGABRT is never success'
    args.out.mkdir(parents=True)
    shutil.copy2(args.batch, args.out / 'batch.jsonl')
    for name in ('deployment.json', 'fleet.log'):
        shutil.copy2(args.runtime / name, args.out / name)
    source = args.out / 'source'
    for rel in deployment['source_sha256']:
        target = source / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args.workspace / rel, target)
    episodes = []
    for row in batch:
        path = Path(row['episode'])
        target = args.out / 'episodes' / path.name
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(path, target)
        episode = json.loads(target.read_text())
        audit = audit_routing_episode(episode, deployment)
        assert audit['ok'] and audit == row['routing_audit'], audit
        assert audit['fast_selected'] > 0 and audit['fast_tokens'] > 0
        assert episode['runtime_fingerprint'] == deployment['runtime_fingerprint']
        episodes.append(episode)
    run_ids = {episode['run_id'] for episode in episodes}
    flat = select_lines(args.log_root / 'decisions.jsonl', args.out / 'decisions.jsonl',
                        lambda row: row.get('run_id') in run_ids)
    transport = select_lines(args.log_root / 'skill_transport.jsonl', args.out / 'skill_transport.jsonl',
                             lambda row: row.get('task_run_id') in run_ids)
    sends = [row for row in transport if row['event'] == 'goal_send_requested']
    replies = [row for row in transport if row['event'] == 'goal_response']
    assert len(sends) == len(replies)
    assert all(row.get('accepted') is True for row in replies)
    assert all(row['event'] in ('goal_send_requested', 'goal_response') for row in transport)
    assert {row['goal_uuid'] for row in sends} == {row['goal_uuid'] for row in replies}
    assert len({row['goal_uuid'] for row in sends}) == len(sends)
    observe_ids = {row['goal_uuid'] for row in sends if 'OBSERVE' in row['label']}
    observer = select_lines(args.log_root / 'observe.jsonl', args.out / 'observe.jsonl',
                            lambda row: row.get('goal_uuid') in observe_ids)
    assert {row['goal_uuid'] for row in observer if row.get('event') == 'goal_execute_started'} == observe_ids
    assert {row['goal_uuid'] for row in observer if 'outcome' in row} == observe_ids
    evidence_ids = {step['executor_result']['evidence_id'] for episode in episodes
                    for step in episode['steps'] if step.get('executor_result')}
    for name in ('pick', 'place', 'verify'):
        select_lines(args.log_root / (name + '.jsonl'), args.out / (name + '.jsonl'),
                     lambda row: row.get('evidence_id') in evidence_ids)
    # Carry logs lack run IDs; preserve a continuous byte range bracketed by
    # monotonic pin records, including un-timestamped engage/release events.
    lines = (args.log_root / 'carry.jsonl').read_bytes().splitlines(keepends=True)
    lo, hi = min(row['mono_ns'] for row in sends), max(row['mono_ns'] for row in replies) + 90_000_000_000
    wall_lo = min(row['wall_ts'] for row in sends) - 120
    wall_hi = max(row['wall_ts'] for row in replies) + 120
    # A wall-date fence separates previous boots whose monotonic counters
    # overlap. Wall time is never used to compute decision latency.
    indices = [i for i, line in enumerate(lines)
               if lo <= json.loads(line).get('request_mono_ns', -1) <= hi
               and wall_lo <= json.loads(line).get('wall_ts', -1) <= wall_hi]
    if indices:
        (args.out / 'carry.jsonl').write_bytes(b''.join(lines[max(0, min(indices)-2):max(indices)+3]))
    indexed = {(row['run_id'], row['seq']): row for row in flat}
    assert len(indexed) == len(flat) == sum(len(episode['steps']) for episode in episodes)
    latencies, outcomes = [], []
    for episode, row in zip(episodes, batch):
        for step in episode['steps']:
            decision = indexed[(episode['run_id'], step['seq'])]
            for field in ('action', 'target', 'confidence', 'policy_trace'):
                assert _sanitize(decision[field]) == step['policy_output'][field]
            if step['policy_input']['world_state_canonical'] is not None:
                assert step['decide_latency_clock'] == 'perf_counter_ns'
                assert type(step['decide_latency_ms']) is float and step['decide_latency_ms'] > 0
                latencies.append(step['decide_latency_ms'])
        outcomes.append(dict(run_id=episode['run_id'], outcome=row['outcome'],
                             command_rc=row['rc'], final_state=episode['final_state'],
                             routing_audit=row['routing_audit'], episode_sha256=digest(Path(row['episode']))))
    report = dict(schema_version=1, routing_ok=True, physical_successes=sum(row['outcome']=='SUCCEEDED' for row in batch),
                  episodes=5, runtime_fingerprint=deployment['runtime_fingerprint'],
                  calibration_sha256=deployment['active_backends']['fast']['calibration_sha256'],
                  fast_selected=sum(row['routing_audit']['fast_selected'] for row in batch),
                  slow_selected=sum(row['routing_audit']['slow_selected'] for row in batch),
                  fast_calls=sum(row['routing_audit']['fast_calls'] for row in batch),
                  fast_tokens=sum(row['routing_audit']['fast_tokens'] for row in batch),
                  harness_errors=[row['harness_error'] for row in batch if row['harness_error']],
                  goal_requests=len(sends), goal_responses=len(replies), sendgoal_timeouts=0,
                  observer_goals_correlated=len(observe_ids), failures_retained=True, resampled_episodes=0,
                  offline_gpu_overlap=args.offline_overlap, outcomes=outcomes,
                  latency=dict(status='MEASURED', clock='perf_counter_ns', **latency_summary(latencies)),
                  latency_comparison='NOT_RUN: no causal latency claim across fingerprints or overlapping GPU traffic',
                  scope='Same-fingerprint S1 n=5 only; frozen large batches remain NOT_RUN')
    (args.out / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('outcomes','latency')}, indent=2))


if __name__ == '__main__':
    main()
