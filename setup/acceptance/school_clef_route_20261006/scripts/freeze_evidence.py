#!/usr/bin/env python3
"""Freeze calibration and completed live routing evidence without deleting it."""
import hashlib
import json
from pathlib import Path
import re
import shutil

from flexcell_skills.contracts.metrics import latency_summary
from flexcell_skills.contracts.routing_audit import audit_routing_episode


def main():
    repo = Path('/home/ros/agentic_workcell_ws')
    root = Path('/home/ros/fc_sync_logs/clef_route_20261006')
    archive = repo / 'setup/acceptance/school_clef_route_20261006'
    assert not (archive / 'SHA256SUMS.json').exists()
    live = json.loads((root / 'live_audit_verified.json').read_text())
    runtime = Path(live['runtime'])
    deployment = json.loads((runtime / 'deployment.json').read_text())
    batch_paths = re.findall(r'batch summary: (.+)', (root / 's1_n5.log').read_text())
    assert len(batch_paths) == 1, 'Do not freeze an active or incomplete batch'
    batch_path = Path(batch_paths[0])
    rows = [json.loads(line) for line in batch_path.read_text().splitlines() if line]
    assert len(rows) == 5, 'Keep partial batches as failures; do not claim n=5'
    counts = dict(episodes=0, physical_successes=0, physical_failures=0,
                  harness_errors=0, routing_errors=0, bootstrap=0, fast_calls=0,
                  fast_tokens=0, fast_selected=0, slow_selected=0, fsm_fallbacks=0)
    details, latencies = [], []
    latency_by_source = {'jev': [], 'llm': []}
    for row in rows:
        assert row['rc'] not in (-6, 134), 'Never accept SIGABRT'
        assert row['reset_rc'] not in (-6, 134)
        reset = json.JSONDecoder().raw_decode(row['reset_output'].lstrip())[0]
        assert reset['ok'] is True

        def reject_abort(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key in ('rc', 'worker_rc', 'returncode'):
                        assert child not in (-6, 134), 'Nested worker SIGABRT'
                    reject_abort(child)
            elif isinstance(value, list):
                for child in value:
                    reject_abort(child)

        reject_abort(reset)
        if row['outcome'] == 'HARNESS_ERROR':
            counts['harness_errors'] += 1
        detail = dict(run=row['run'], rc=row['rc'], outcome=row['outcome'],
                      harness_error=row['harness_error'], episode=row['episode'])
        if row['episode']:
            record = json.loads(Path(row['episode']).read_text())
            audit = audit_routing_episode(record, deployment)
            assert audit == row['routing_audit']
            assert record['runtime_fingerprint'] == live['runtime_fingerprint']
            counts['episodes'] += 1
            counts['physical_successes' if str(record['final_state']['outcome']) == '0'
                   else 'physical_failures'] += 1
            counts['routing_errors'] += not audit['ok']
            for field in ('bootstrap', 'fast_calls', 'fast_tokens', 'fast_selected',
                          'slow_selected', 'fsm_fallbacks'):
                counts[field] += audit[field]
            detail.update(routing_audit=audit, final_state=record['final_state'])
            for step in record['steps']:
                if step['policy_input']['world_state_canonical'] is not None:
                    assert step['decide_latency_clock'] == 'perf_counter_ns'
                    value = step['decide_latency_ms']
                    assert type(value) is float and value > 0
                    latencies.append(value)
                    source = step['policy_output']['policy_trace']['source']
                    if source in latency_by_source:
                        latency_by_source[source].append(value)
        details.append(detail)
    summary = dict(schema_version=1, stage='smoke', scenario='S1', planned_n=5,
                   batch=str(batch_path), batch_command_rc=int((root / 's1_n5.rc').read_text()),
                   runtime_fingerprint=live['runtime_fingerprint'],
                   calibration_sha256=live['calibration_sha256'],
                   routing_ok=counts['routing_errors'] == counts['harness_errors'] == 0,
                   physical_ok=counts['physical_successes'] == 5,
                   counts=counts, runs=details,
                   decision_latency=dict(status='MEASURED', clock='perf_counter_ns',
                                         bootstrap_excluded=True, **latency_summary(latencies)),
                   decision_latency_by_selected_source={
                       source: latency_summary(values) if values else {'status': 'NOT_RUN'}
                       for source, values in latency_by_source.items()},
                   limitations='Five episodes; historical calibration and current physical results are separate; no n>=50 collection')
    assert not (root / 's1_n5_audit.json').exists()
    (root / 's1_n5_audit.json').write_text(json.dumps(summary, indent=2) + '\n')
    receipt = []

    def freeze(source, relative):
        target = archive / relative
        assert not target.exists(), target
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        data = source.read_bytes()
        assert target.read_bytes() == data
        receipt.append(dict(original=str(source), copy=relative, bytes=len(data),
                            sha256=hashlib.sha256(data).hexdigest()))

    for source in sorted(root.iterdir()):
        if source.is_file():
            freeze(source, 'run/' + source.name)
    for folder in ('pilot_inputs', 'extension_inputs', 'smoke'):
        for source in sorted((root / folder).iterdir()):
            if source.is_file():
                freeze(source, 'run/' + folder + '/' + source.name)
    freeze(runtime / 'deployment.json', 'deployment.json')
    freeze(runtime / 'fleet.log', 'fleet.log')
    freeze(Path(live['episode_file']), 'episodes/' + Path(live['episode_file']).name)
    freeze(batch_path, 'batches/' + batch_path.name)
    for row in rows:
        if row['episode']:
            path = Path(row['episode'])
            freeze(path, 'episodes/' + path.name)
    for source in sorted((archive / 'scripts').glob('*')):
        if source.is_file():
            data = source.read_bytes()
            receipt.append(dict(original=str(source), copy='scripts/' + source.name,
                                bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    (archive / 'SHA256SUMS.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
