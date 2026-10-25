#!/usr/bin/env python3
"""Verify the CLEF-RECORDED-001 receipt against bytes in this checkout.

Pure stdlib.  No ROS, no network, no model.  The receipt was produced by
`setup/model_validation/run_clef_replay.py` against the household RX 6800
Vulkan service; this script re-derives every machine-checkable claim from the
files committed next to it.

What this script deliberately does NOT claim
--------------------------------------------
The captured instance log has no per-layer offload line. This does not establish
what the build can emit or the GPU residency of this instance. The module list
and adapter-wide memory snapshot are supporting observations, not per-process
layer counts. Other instances have separate evidence. This receipt keeps
`gpu_execution` at REQUIRES_SERVER_LOG_EVIDENCE.

Exit 0 = every check holds.  1 = a check failed.  2 = the archive is unusable.
"""

import hashlib
import json
import math
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REPORT = HERE / 'clef_20261024T131429Z.json'
LOG = HERE / 'llama-server-instance.log'
GPU = HERE / 'gpu_evidence.json'
MANIFEST = ROOT / 'setup/model_validation/clef-inputs.json'
INPUTS_SHA = 'b507b08e55148b8a2004fd5b8fc74b738997eaa7b3e41906aa7493308d824ca4'
ACTIONS = {'ABORT', 'OBSERVE', 'PICK', 'PLACE', 'VERIFY', 'WAIT'}

# The identity fixed by docs/MODEL_IDENTITY.md and re-stated by the task.
Q8_SHA = '8754b06f7d16d6d6ab63493b2ee385cc0ed6abde8c25c39298dc3e1eb05593d9'
Q8_PATH_WIN = 'F:\\flexcell-models\\Clef-Flash-Q8_0.gguf'
GIB = 1024 ** 3


class Ledger:
    def __init__(self):
        self.rows = []

    def add(self, name, ok, detail=''):
        self.rows.append((name, bool(ok), detail))
        return ok

    def failed(self):
        return [r for r in self.rows if not r[1]]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load():
    for path in (REPORT, LOG, GPU):
        if not path.is_file():
            print('MISSING ARTIFACT: %s' % path)
            sys.exit(2)
    with open(REPORT, encoding='utf-8') as fh:
        report = json.load(fh)
    with open(GPU, encoding='utf-8') as fh:
        gpu = json.load(fh)
    log = LOG.read_text(encoding='utf-8', errors='replace')
    return report, gpu, log


def parse_answers(row):
    """Return the decoded response payload, or None if it is not JSON."""
    payload = row.get('response_json')
    if isinstance(payload, dict):
        return payload
    if not isinstance(payload, str):
        return None
    try:
        return json.loads(payload)
    except ValueError:
        return None


def mapping(value):
    return value if isinstance(value, dict) else {}


def finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def measured_count(value):
    return type(value) is int and value >= 0


def frozen_inputs():
    """Read only the pinned input manifest, never a path supplied by a row."""
    if sha256_file(MANIFEST) != INPUTS_SHA:
        raise ValueError('input manifest differs from the frozen task')
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    selected = []
    for source in manifest['episodes']:
        path = ROOT / source['path']
        if sha256_file(path) != source['sha256']:
            raise ValueError('source episode hash mismatch: ' + source['path'])
        episode = json.loads(path.read_text(encoding='utf-8'))
        for step in episode['steps']:
            text = step['policy_input']['world_state_canonical']
            if text is not None:
                selected.append({
                    'episode': source['path'], 'episode_sha256': source['sha256'],
                    'seq': step['seq'],
                    'state_sha256': hashlib.sha256(text.encode()).hexdigest(),
                    'recorded_decision': {key: step['policy_output'][key]
                                          for key in ('action', 'target', 'reason_code')},
                })
    selected = selected[:manifest['model_calls']]
    if len(selected) != 20:
        raise ValueError('frozen task must contain 20 non-bootstrap inputs')
    return selected


def check_report(report, ledger):
    ledger.add('status is MODEL_API_PASS', report.get('status') == 'MODEL_API_PASS',
               'status=%r' % report.get('status'))

    rows = report.get('rows') or []
    ledger.add('exactly 20 recorded decisions', len(rows) == 20, 'n=%d' % len(rows))
    ledger.add('every row passed', all(mapping(r).get('pass') is True for r in rows))
    ledger.add('no row carries errors', all(mapping(r).get('errors') == [] for r in rows))
    ledger.add('input manifest digest is the frozen task',
               report.get('input_manifest_sha256') == INPUTS_SHA)
    ledger.add('requested model is the task model',
               report.get('requested_model') == 'clef-flash-q8_0')

    ledger.add('task id is CLEF-RECORDED-001',
               report.get('task_id') == 'CLEF-RECORDED-001', report.get('task_id'))
    ledger.add('repository commit pinned',
               re.fullmatch(r'[0-9a-f]{40}', report.get('repository_commit') or '') is not None,
               str(report.get('repository_commit')))

    local = report.get('local_weight_sha256')
    expected = report.get('expected_local_weight_sha256')
    ledger.add('local weight sha matches the documented Q8 sha', local == Q8_SHA, str(local))
    ledger.add('expected sha equals the documented Q8 sha', expected == Q8_SHA, str(expected))

    ledger.add('no robot commands were sent', report.get('robot_commands_sent') == 0,
               str(report.get('robot_commands_sent')))
    ledger.add('no paid slow-model calls', report.get('paid_slow_model_calls') == 0,
               str(report.get('paid_slow_model_calls')))
    ledger.add('closed-loop success not claimed',
               report.get('closed_loop_success_measured') is False,
               str(report.get('closed_loop_success_measured')))

    # The receipt must keep saying what it cannot see.  A future edit that
    # promotes these to PASS without a log line is exactly the failure mode
    # this archive exists to prevent.
    ledger.add('served weight identity still marked as needing a server check',
               report.get('served_weight_identity') == 'REQUIRES_SERVER_PROCESS_AND_LOG_CHECK',
               str(report.get('served_weight_identity')))
    ledger.add('gpu execution still marked as needing log evidence',
               report.get('gpu_execution') == 'REQUIRES_SERVER_LOG_EVIDENCE',
               str(report.get('gpu_execution')))


def check_rows(report, ledger):
    rows = report.get('rows') or []
    try:
        inputs = frozen_inputs()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        ledger.add('frozen manifest and source episodes verify', False, str(exc))
        return
    ledger.add('frozen manifest and source episodes verify', True)
    # Match every row to its prescribed input, including ordering and state bytes.
    ledger.add('rows match the fixed 20 inputs in order', len(rows) == len(inputs) and all(
        all(mapping(row).get(key) == value for key, value in expected.items())
        for row, expected in zip(rows, inputs)))

    source_ok = model_ok = probs_ok = tokens_ok = actions_ok = agreement_ok = True
    token_total = agreements = 0
    latencies = []
    for raw_row in rows:
        row = mapping(raw_row)
        decision = mapping(row.get('decision'))
        trace = mapping(decision.get('policy_trace'))
        source_ok &= trace.get('source') == 'jev' and trace.get('fallback') is False
        model_ok &= (trace.get('model') == 'clef-flash-q8_0'
                     and trace.get('model_sha256') == Q8_SHA
                     and trace.get('calibration_sha256') == report.get('calibration_sha256'))
        payload = mapping(parse_answers(row))
        model_ok &= payload.get('model') == Q8_PATH_WIN
        answer = mapping(mapping(payload.get('answers')).get('next_action'))
        probs = answer.get('probabilities')
        valid_probs = (isinstance(probs, dict) and set(probs) == ACTIONS
                       and all(finite_number(p) and 0 <= p <= 1 for p in probs.values()))
        probs_ok &= bool(valid_probs and abs(sum(probs.values()) - 1) <= 1e-6)
        choice = answer.get('choice')
        actions_ok &= (isinstance(choice, str) and choice in ACTIONS
                       and decision.get('action') == choice)
        usage = mapping(payload.get('usage'))
        counts = [usage.get('input_tokens'), usage.get('output_tokens')]
        if all(measured_count(n) for n in counts):
            measured = sum(counts)
            token_total += measured
            tokens_ok &= (measured > 0 and measured_count(trace.get('tokens'))
                          and trace.get('tokens') == measured)
        else:
            tokens_ok = False
        expected = mapping(row.get('recorded_decision'))
        agrees = expected == {key: decision.get(key)
                              for key in ('action', 'target', 'reason_code')}
        agreement_ok &= row.get('recorded_action_agreement') is agrees
        agreements += agrees
        latency = row.get('latency_ms')
        if finite_number(latency) and latency >= 0:
            latencies.append(latency)

    ledger.add('every decision is a real Jev proposal without fallback', source_ok)
    ledger.add('response and trace model identities agree with the task', model_ok)
    ledger.add('every distribution has finite normalised action probabilities', probs_ok)
    ledger.add('every decision matches a legal response action', actions_ok)
    ledger.add('each decision has positive measured usage matching trace tokens', tokens_ok)
    summary = mapping(report.get('summary'))
    ledger.add('summary tokens equal recomputed response usage',
               measured_count(summary.get('tokens')) and summary.get('tokens') == token_total
               and token_total > 0, 'recomputed=%d' % token_total)
    ledger.add('summary and attempted call counts match the rows',
               type(summary.get('model_calls')) is int
               and summary.get('model_calls') == len(rows)
               and type(report.get('model_calls_attempted')) is int
               and report.get('model_calls_attempted') == len(rows))
    ledger.add('action agreement flags and summary are recomputed', agreement_ok
               and type(summary.get('recorded_action_agreements')) is int
               and summary.get('recorded_action_agreements') == agreements)
    latency_ok = bool(rows) and len(latencies) == len(rows)
    if latency_ok:
        latencies.sort()
        for key, value in [('p50_ms', statistics.median(latencies)),
                           ('p95_ms_nearest_rank', latencies[math.ceil(.95 * len(rows)) - 1])]:
            got = summary.get(key)
            latency_ok &= finite_number(got) and math.isclose(got, value, abs_tol=1e-6)
    ledger.add('latency summary matches finite recorded latencies', latency_ok)


def check_log(log, ledger):
    ledger.add('instance log names the Q8 model path',
               "loading model '%s'" % Q8_PATH_WIN in log, '')
    ledger.add('instance log shows the server bound to 127.0.0.1:11435',
               'listening on http://127.0.0.1:11435' in log, '')

    releases = len(re.findall(r'slot\s+release:', log))
    ledger.add('instance log records 20 completed slots', releases >= 20,
               'releases=%d' % releases)

    # This is a property of the captured file, not of every run of this build.
    offload_lines = re.findall(r'offload', log, re.IGNORECASE)
    ledger.add('captured instance log has no offload line (instance evidence incomplete)',
               len(offload_lines) == 0,
               'offload_mentions=%d' % len(offload_lines))


def check_gpu(gpu, ledger):
    proc = gpu.get('process') or {}
    cmd = proc.get('command_line') or ''

    ledger.add('snapshot names a pid', isinstance(proc.get('pid'), int)
               and proc['pid'] > 0, str(proc.get('pid')))
    ledger.add('evidence names the server executable',
               (proc.get('executable_path') or '').endswith('llama-server.exe'),
               str(proc.get('executable_path')))
    ledger.add('command line pins -ngl 99', '-ngl 99' in cmd, '')
    ledger.add('command line pins the same Q8 GGUF', Q8_PATH_WIN in cmd, '')
    ledger.add('command line pins port 11435', '--port 11435' in cmd, '')

    mods = set(gpu.get('loaded_gpu_modules') or [])
    ledger.add('process loaded the Vulkan backend',
               'ggml-vulkan.dll' in mods, ','.join(sorted(mods)))
    ledger.add('process loaded the system Vulkan loader',
               'vulkan-1.dll' in mods, '')

    adapter = (gpu.get('gpu') or {})
    used = adapter.get('dedicated_usage_bytes') or 0
    # Adapter-wide memory does not identify per-process layer residency.
    ledger.add('snapshot records adapter-wide usage above 8 GiB',
               used > 8 * GIB, 'dedicated=%.2f GiB' % (used / GIB))
    ledger.add('adapter is a discrete Radeon',
               'Radeon' in (adapter.get('adapter_name') or ''),
               str(adapter.get('adapter_name')))


def main():
    report, gpu, log = load()
    ledger = Ledger()
    check_report(report, ledger)
    check_rows(report, ledger)
    check_log(log, ledger)
    check_gpu(gpu, ledger)

    width = max(len(r[0]) for r in ledger.rows)
    for name, ok, detail in ledger.rows:
        print('%-*s %s%s' % (width, name, 'PASS' if ok else 'FAIL',
                             ('  (' + detail + ')') if detail else ''))

    failed = ledger.failed()
    print()
    if failed:
        print('CLEF-RECORDED-001 RECEIPT: REJECTED (%d of %d checks failed)'
              % (len(failed), len(ledger.rows)))
        return 1
    print('CLEF-RECORDED-001 RECEIPT: CONFIRMED (%d checks)'
          % len(ledger.rows))
    print('model interface: PASS | GPU layer residency: UNKNOWN (no log line) | '
          'routing: NOT_TESTED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
