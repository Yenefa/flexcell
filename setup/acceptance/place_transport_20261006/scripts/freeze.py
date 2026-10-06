#!/usr/bin/env python3
"""Retain one bounded batch and audit task/controller UUIDs and PLACE checks."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shutil

from flexcell_skills.contracts.episode import _sanitize
from flexcell_skills.contracts.metrics import latency_summary
from flexcell_skills.contracts.routing_audit import audit_routing_episode


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_bytes().splitlines() if line.strip()]


def retain(source, target, predicate):
    if not source.exists():
        target.write_bytes(b'')
        return []
    selected = [line for line in source.read_bytes().splitlines(keepends=True)
                if line.strip() and predicate(json.loads(line))]
    target.write_bytes(b''.join(selected))
    return [json.loads(line) for line in selected]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--batch', type=Path, required=True)
    ap.add_argument('--runtime', type=Path, required=True)
    ap.add_argument('--offsets', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    assert not args.out.exists(), 'Preserve previous evidence'
    workspace = Path('/home/ros/agentic_workcell_ws')
    log_root = Path.home() / '.ros/flexcell'
    deployment = json.loads((args.runtime / 'deployment.json').read_text())
    for rel, expected in {**deployment['source_sha256'], **deployment['harness_sha256']}.items():
        assert digest(workspace / rel) == expected, rel
    installed = Path(deployment['install']) / 'flexcell_skills/lib/python3.12/site-packages/flexcell_skills'
    for rel, expected in deployment['installed_source_sha256'].items():
        assert digest(installed / rel) == expected, rel
    profile = {k: v for k, v in deployment.items() if k not in ('runtime_fingerprint', 'head', 'install')}
    assert hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest() == deployment['runtime_fingerprint']
    batch = rows(args.batch)
    assert 0 < len(batch) <= 5 and all(row['scenario'] == 'S1' for row in batch)
    assert all(row['runtime_fingerprint'] == deployment['runtime_fingerprint']
               or (row['episode'] is None and row['harness_error']) for row in batch)
    args.out.mkdir(parents=True)
    shutil.copy2(args.batch, args.out / 'batch.jsonl')
    shutil.copy2(args.offsets, args.out / 'offsets.json')
    for name in ('deployment.json', 'fleet.log', 'gazebo.log', 'moveit.log', 'move_to_pose.log'):
        shutil.copy2(args.runtime / name, args.out / name)
    for rel in {**deployment['source_sha256'], **deployment['harness_sha256']}:
        target = args.out / 'source' / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(workspace / rel, target)
    dds = workspace / 'setup/cyclone_wsl_local.xml'
    assert digest(dds) == deployment['dds_profile_sha256']
    shutil.copy2(dds, args.out / 'source/setup/cyclone_wsl_local.xml')
    # Preserve raw byte tails, including failures without an episode/run ID.
    tails = args.out / 'raw'
    tails.mkdir()
    for name, offset in json.loads(args.offsets.read_text())['log_offsets'].items():
        path = log_root / name
        assert not path.exists() or path.stat().st_size >= offset, 'Log truncated: ' + name
        (tails / name).write_bytes(path.read_bytes()[offset:] if path.exists() else b'')
    episodes, audits = [], []
    for row in batch:
        if not row['episode']:
            continue
        source = Path(row['episode'])
        target = args.out / 'episodes' / source.name
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(source, target)
        episode = json.loads(target.read_text())
        assert episode['runtime_fingerprint'] == deployment['runtime_fingerprint']
        audit = audit_routing_episode(episode, deployment)
        assert audit == row['routing_audit'], 'Runner audit changed'
        episodes.append(episode)
        audits.append(audit)
    run_ids = {episode['run_id'] for episode in episodes}
    flat = retain(log_root / 'decisions.jsonl', args.out / 'decisions.jsonl',
                  lambda row: row.get('run_id') in run_ids)
    task = retain(log_root / 'skill_transport.jsonl', args.out / 'skill_transport.jsonl',
                  lambda row: row.get('task_run_id') in run_ids)
    sends = [row for row in task if row['event'] == 'goal_send_requested']
    replies = [row for row in task if row['event'] == 'goal_response']
    task_confirmed = (len(sends) == len(replies)
                      and all(row.get('accepted') is True for row in replies)
                      and Counter(row['goal_uuid'] for row in sends) == Counter(row['goal_uuid'] for row in replies)
                      and len({row['goal_uuid'] for row in sends}) == len(sends)
                      and all(row['event'] in ('goal_send_requested', 'goal_response') for row in task))
    observe_ids = {row['goal_uuid'] for row in sends if 'OBSERVE' in row['label']}
    observer = retain(log_root / 'observe.jsonl', args.out / 'observe.jsonl',
                      lambda row: row.get('goal_uuid') in observe_ids)
    observer_correlated = ({row['goal_uuid'] for row in observer if row.get('event') == 'goal_execute_started'} == observe_ids
                           and {row['goal_uuid'] for row in observer if 'outcome' in row} == observe_ids)
    evidence_ids = {step['executor_result']['evidence_id'] for ep in episodes
                    for step in ep['steps'] if step.get('executor_result')}
    skill_rows = {}
    for name in ('pick', 'place', 'verify'):
        skill_rows[name] = retain(log_root / (name + '.jsonl'), args.out / (name + '.jsonl'),
                                 lambda row: row.get('evidence_id') in evidence_ids)
    controller = rows(tails / 'controller_transport.jsonl')
    by_uuid = defaultdict(list)
    for row in controller:
        by_uuid[row['controller_goal_uuid']].append(row)
    controller_errors = []
    for goal_id, events in by_uuid.items():
        names = Counter(row['event'] for row in events)
        if names != Counter(controller_goal_send_requested=1, controller_goal_response=1, controller_goal_terminal=1):
            controller_errors.append(dict(goal_uuid=goal_id, events=dict(names)))
        elif not all(row.get('accepted') is True for row in events if row['event']=='controller_goal_response'):
            controller_errors.append(dict(goal_uuid=goal_id, error='Rejected controller goal'))
        elif not all(row['status'] in (4, 5, 6) for row in events if row['event']=='controller_goal_terminal'):
            controller_errors.append(dict(goal_uuid=goal_id, error='Nonterminal result'))
        if len({(row['request_id'], row['evidence_id']) for row in events}) != 1:
            controller_errors.append(dict(goal_uuid=goal_id, error='Request identity changed'))
    controller_evidence = {row['evidence_id'] for row in controller}
    motions = retain(tails / 'move_to_pose.jsonl', args.out / 'move_to_pose.jsonl',
                    lambda row: row.get('evidence_id') in controller_evidence)
    assert {row['evidence_id'] for row in motions} == controller_evidence, 'Controller lacks motion record'
    places = skill_rows['place']
    checks = [check for row in places for check in row.get('release_ready_checks', [])]
    negative_dependencies = rows(tails / 'place_dependency.jsonl')
    indexed = {(row['run_id'], row['seq']): row for row in flat}
    assert len(indexed) == len(flat) == sum(len(ep['steps']) for ep in episodes)
    latencies = []
    for episode in episodes:
        for step in episode['steps']:
            decision = indexed[(episode['run_id'], step['seq'])]
            for field in ('action', 'target', 'confidence', 'policy_trace'):
                assert _sanitize(decision[field]) == step['policy_output'][field]
            if step['policy_input']['world_state_canonical'] is not None:
                assert step['decide_latency_clock'] == 'perf_counter_ns'
                assert type(step['decide_latency_ms']) is float and step['decide_latency_ms'] > 0
                latencies.append(step['decide_latency_ms'])
    report = dict(schema_version=1, episodes=len(episodes), batch_rows=len(batch), planned_episodes=5,
                  routing_ok=bool(audits) and all(a['ok'] and a['fast_selected']>0 and a['fast_tokens']>0 for a in audits),
                  physical_successes=sum(row['outcome']=='SUCCEEDED' and row['rc'] not in (-6, 134) for row in batch),
                  runtime_fingerprint=deployment['runtime_fingerprint'],
                  calibration_sha256=deployment['active_backends']['fast']['calibration_sha256'],
                  fast_selected=sum(a['fast_selected'] for a in audits),
                  slow_selected=sum(a['slow_selected'] for a in audits),
                  fast_calls=sum(a['fast_calls'] for a in audits), fast_tokens=sum(a['fast_tokens'] for a in audits),
                  harness_errors=[row['harness_error'] for row in batch if row['harness_error']],
                  task_goal_requests=len(sends), task_goal_responses=len(replies), task_transport_ok=task_confirmed,
                  observer_goals=len(observe_ids), observer_correlated=observer_correlated,
                  controller_goals=len(by_uuid), controller_transport_ok=bool(by_uuid) and not controller_errors,
                  controller_errors=controller_errors,
                  controller_terminal_statuses=dict(Counter(str(r['status']) for r in controller if r['event']=='controller_goal_terminal')),
                  controller_quarantines=sum(r['event']=='controller_goal_quarantined' for r in controller),
                  places=len(places), place_dependency_checks=len(checks),
                  place_check_phases=dict(Counter(c['phase'] for c in checks)),
                  place_checks_ready=sum(c['ready'] for c in checks),
                  negative_dependency_events=len(negative_dependencies),
                  failures_retained=True, resampled_episodes=0, offline_gpu_overlap=False,
                  outcomes=[dict(run=row['run'], outcome=row['outcome'], command_rc=row['rc'],
                                 episode=Path(row['episode']).name if row['episode'] else None) for row in batch],
                  latency=dict(status='MEASURED', clock='perf_counter_ns', **latency_summary(latencies)) if latencies else dict(status='NOT_RUN'),
                  latency_comparison='NOT_RUN: different fingerprints; no causal latency comparison',
                  root_cause_of_prior_transport_failures='UNKNOWN: a passing local profile does not establish prior NIC/RMW cause',
                  scope='One same-fingerprint S1 n<=5 simulation batch. No physical hardware acceptance. n>=50 remains frozen.')
    (args.out / 'audit.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
