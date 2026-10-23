#!/usr/bin/env python3
"""Send frozen recorded inputs to the existing Clef service. No ROS or torch.

This is a model API smoke, not a physical task or same-runtime model replay.
GPU offload and the served weight path require separate server-log evidence.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
import traceback
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
# Use this checkout's pure policy modules, not a stale installed ROS workspace.
sys.path.insert(0, str(ROOT / 'src/flexcell/flexcell_skills'))

from flexcell_skills.canonical_state import deserialize_envelope
from flexcell_skills.confidence_calibration import prompt_digest
from flexcell_skills.contracts.episode import (
    _constraints_from_dict, _goal_from_dict, _history_from_dicts, decision_to_dict)
from flexcell_skills.jev_backends import ClefBackend
from flexcell_skills.jev_policy import JevPolicy

Q8_SHA = '8754b06f7d16d6d6ab63493b2ee385cc0ed6abde8c25c39298dc3e1eb05593d9'


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def git_revision():
    try:
        return subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL, timeout=5).strip()
    except (OSError, subprocess.SubprocessError):
        return None


class RecordingClefBackend(ClefBackend):
    """Use the production HTTP client and retain each actual exchange."""

    def _http_transport(self, url, payload, timeout_s):
        self.last_payload = payload
        self.last_response = None
        response = super()._http_transport(url, payload, timeout_s)
        self.last_response = response
        return response


def run(args, report, save):
    if sha(args.weights) != Q8_SHA:
        raise ValueError('Local GGUF does not match the documented Q8 weight SHA')
    report['local_weight_sha256'] = Q8_SHA
    manifest_path = HERE / 'clef-inputs.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    report['input_manifest_sha256'] = sha(manifest_path)
    selected = []
    for source in manifest['episodes']:
        path = ROOT / source['path']
        if sha(path) != source['sha256']:
            raise ValueError('Archived episode hash mismatch: ' + source['path'])
        episode = json.loads(path.read_text(encoding='utf-8'))
        for step in episode['steps']:
            if step['policy_input']['world_state_canonical'] is not None:
                selected.append((source, step))
    selected = selected[:manifest['model_calls']]
    if len(selected) != 20:
        raise ValueError('Expected the fixed set of 20 recorded model inputs')

    os.environ['FLEXCELL_JEV_ENDPOINT'] = args.endpoint
    os.environ['FLEXCELL_JEV_MODEL'] = args.model
    os.environ['FLEXCELL_JEV_MODEL_SHA256'] = Q8_SHA
    backend = RecordingClefBackend(timeout_s=args.timeout_s)
    policy = JevPolicy(backend)
    report['prompt_sha256'] = prompt_digest()
    report['calibration_sha256'] = policy.calibration_sha256
    # Lack of route calibration does not invalidate a typed API response.
    report['routing_qualification'] = 'NOT_TESTED'
    for source, step in selected:
        pi = step['policy_input']
        text = pi['world_state_canonical']
        deserialize_envelope(text)
        started = time.perf_counter()
        decision = policy.decide(
            json.loads(text), _goal_from_dict(pi['goal']),
            _constraints_from_dict(pi['constraints']),
            _history_from_dicts(pi['history']))
        latency = (time.perf_counter() - started) * 1000
        trace = decision.policy_trace or {}
        response = backend.last_response
        failures = []
        if trace.get('source') != 'jev' or trace.get('fallback') is not False:
            failures.append('No real Clef proposal; FSM fallback is not a pass')
        if not isinstance(trace.get('tokens'), int) or trace['tokens'] <= 0:
            failures.append('Missing positive measured token usage')
        if trace.get('model') != args.model or trace.get('model_sha256') != Q8_SHA:
            failures.append('Client model identity mismatch')
        if backend.last_payload['state'] != text:
            failures.append('Canonical state bytes changed')
        answers = response.get('answers') if isinstance(response, dict) else None
        answer = answers.get('next_action') if isinstance(answers, dict) else None
        probabilities = answer.get('probabilities') if isinstance(answer, dict) else None
        if (not isinstance(probabilities, dict) or not probabilities
                or any(isinstance(v, bool) or not isinstance(v, (int, float))
                       or not math.isfinite(v) or not 0 <= v <= 1
                       for v in probabilities.values())
                or abs(sum(probabilities.values()) - 1) > 0.001):
            failures.append('Missing or invalid probability distribution')
        expected = {k: step['policy_output'][k] for k in ('action', 'target', 'reason_code')}
        got = {k: getattr(decision, k) for k in expected}
        row = {
            'episode': source['path'], 'episode_sha256': source['sha256'],
            'seq': step['seq'],
            'state_sha256': hashlib.sha256(text.encode()).hexdigest(),
            'latency_ms': latency, 'recorded_decision': expected,
            'decision': decision_to_dict(decision),
            'recorded_action_agreement': expected == got,
            # Preserve a malformed/non-finite response as text in valid report JSON.
            'response_json': json.dumps(response, ensure_ascii=False),
            'pass': not failures, 'errors': failures,
        }
        report['rows'].append(row)
        report['model_calls_attempted'] = len(report['rows'])
        save()
        print(f"{len(report['rows'])}/20: {'PASS' if row['pass'] else 'FAIL'} {latency:.1f}ms", flush=True)
        if failures:
            raise RuntimeError('; '.join(failures))
    latencies = sorted(row['latency_ms'] for row in report['rows'])
    report['summary'] = {
        'model_calls': len(latencies),
        'p50_ms': statistics.median(latencies),
        'p95_ms_nearest_rank': latencies[math.ceil(0.95 * len(latencies)) - 1],
        'tokens': policy.stats['tokens'],
        'recorded_action_agreements': sum(row['recorded_action_agreement'] for row in report['rows']),
        'note': 'Agreement is descriptive; it is not a physical success rate.',
    }
    report['status'] = 'MODEL_API_PASS'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--weights', type=Path, required=True, help='Existing Q8 GGUF; read only')
    parser.add_argument('--endpoint', default='http://127.0.0.1:11435/v1/systemone')
    parser.add_argument('--model', default='clef-flash-q8_0')
    parser.add_argument('--timeout-s', type=float, default=10.0)
    parser.add_argument('--out', type=Path, required=True, help='New report path; never overwritten')
    args = parser.parse_args(argv)
    endpoint = urlparse(args.endpoint)
    if (endpoint.scheme not in ('http', 'https') or not endpoint.hostname
            or endpoint.username or endpoint.password or endpoint.query
            or endpoint.path != '/v1/systemone'):
        parser.error('--endpoint must be a typed /v1/systemone HTTP endpoint without credentials')
    if not math.isfinite(args.timeout_s) or not 0 < args.timeout_s <= 30:
        parser.error('--timeout-s must be >0 and <=30')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    try:
        stream = args.out.open('x', encoding='utf-8')
    except FileExistsError:
        print('Report already exists; use a new output path.', file=sys.stderr)
        return 2
    report = {
        'task_id': 'CLEF-RECORDED-001',
        'kind': 'RECORDED_INPUT_MODEL_API_SMOKE',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'repository_commit': git_revision(), 'platform': platform.platform(),
        'python_version': sys.version, 'endpoint': args.endpoint,
        'requested_model': args.model, 'expected_local_weight_sha256': Q8_SHA,
        'served_weight_identity': 'REQUIRES_SERVER_PROCESS_AND_LOG_CHECK',
        'gpu_execution': 'REQUIRES_SERVER_LOG_EVIDENCE',
        'robot_commands_sent': 0, 'paid_slow_model_calls': 0,
        'closed_loop_success_measured': False,
        'model_calls_attempted': 0, 'rows': [], 'status': 'RUNNING',
    }

    def save():
        stream.seek(0)
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
        stream.truncate()
        stream.flush()

    with stream:
        save()
        try:
            run(args, report, save)
        except Exception as exc:
            report.update(status='FAIL', error=str(exc), traceback=traceback.format_exc())
        except KeyboardInterrupt:
            report['status'] = 'INTERRUPTED'
        save()
    print(json.dumps({'status': report['status'], 'report': str(args.out)}), flush=True)
    return 0 if report['status'] == 'MODEL_API_PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
