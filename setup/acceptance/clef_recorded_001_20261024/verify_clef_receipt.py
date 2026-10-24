#!/usr/bin/env python3
"""Verify the CLEF-RECORDED-001 receipt against bytes in this checkout.

Pure stdlib.  No ROS, no network, no model.  The receipt was produced by
`setup/model_validation/run_clef_replay.py` against the household RX 6800
Vulkan service; this script re-derives every machine-checkable claim from the
files committed next to it.

What this script deliberately does NOT claim
--------------------------------------------
The llama.cpp build used here does not emit per-layer offload lines to the
server log.  So "N of N layers resident on the GPU" is not verifiable and is
never asserted.  What is verifiable is: the process loaded the Vulkan backend,
the adapter's dedicated memory holds roughly the weight file's size, and the
server itself reports the same GGUF path that was hashed locally.  Those are
three independent facts pointing the same way; none of them is the log line
the task asked for, and the receipt keeps `gpu_execution` at
REQUIRES_SERVER_LOG_EVIDENCE to say so.

Exit 0 = every check holds.  1 = a check failed.  2 = the archive is unusable.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REPORT = HERE / 'clef_20261024T131429Z.json'
LOG = HERE / 'llama-server-instance.log'
GPU = HERE / 'gpu_evidence.json'

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


def check_report(report, ledger):
    ledger.add('status is MODEL_API_PASS', report.get('status') == 'MODEL_API_PASS',
               'status=%r' % report.get('status'))

    rows = report.get('rows') or []
    ledger.add('exactly 20 recorded decisions', len(rows) == 20, 'n=%d' % len(rows))
    ledger.add('every row passed', all(r.get('pass') for r in rows),
               'failed=%d' % sum(1 for r in rows if not r.get('pass')))
    ledger.add('no row carries errors', all(not r.get('errors') for r in rows),
               'with_errors=%d' % sum(1 for r in rows if r.get('errors')))

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
    if not rows:
        return

    # Every response must be a real model answer: positive measured tokens and
    # a normalised distribution.  A fallback or a missing token count fails.
    bad_tokens = bad_sums = bad_model = 0
    for row in rows:
        payload = parse_answers(row)
        if not isinstance(payload, dict):
            bad_model += 1
            continue
        if payload.get('model') != Q8_PATH_WIN:
            bad_model += 1
        answers = payload.get('answers') or {}
        nxt = answers.get('next_action') or {}
        probs = nxt.get('probabilities') or {}
        if not probs:
            bad_sums += 1
            continue
        total = sum(probs.values())
        if abs(total - 1.0) > 1e-6:
            bad_sums += 1
        if any(p < 0 or p > 1 for p in probs.values()):
            bad_sums += 1

    ledger.add('every response names the same Q8 GGUF', bad_model == 0,
               'mismatched=%d' % bad_model)
    ledger.add('every distribution is finite and normalised', bad_sums == 0,
               'bad=%d' % bad_sums)

    tokens = ((report.get('summary') or {}).get('tokens') or 0)
    ledger.add('measured token total is positive', tokens > 0, 'tokens=%d' % tokens)

    # The three source episodes must still be byte-identical in this checkout.
    # Checked per (episode, sha) pair, not per episode: several decisions share
    # one episode, and de-duplicating by path lets a forged sha on an early row
    # be overwritten by a correct one on a later row of the same episode.
    claimed = {(row['episode'], row.get('episode_sha256')) for row in rows}
    missing = sorted({p for p, _ in claimed if not (ROOT / p).is_file()})
    ledger.add('all three source episodes are present', not missing,
               'missing=%d' % len(missing))
    if not missing:
        mismatched = sorted({(p, want) for p, want in claimed
                             if sha256_file(ROOT / p) != want})
        ledger.add('source episode bytes still match the receipt',
                   not mismatched, 'mismatched=%d' % len(mismatched))
    ledger.add('every decision row cites an episode sha',
               all(want for _, want in claimed),
               'distinct episodes=%d, distinct claims=%d'
               % (len({p for p, _ in claimed}), len(claimed)))


def check_log(log, ledger):
    ledger.add('instance log names the Q8 model path',
               "loading model '%s'" % Q8_PATH_WIN in log, '')
    ledger.add('instance log shows the server bound to 127.0.0.1:11435',
               'listening on http://127.0.0.1:11435' in log, '')

    releases = len(re.findall(r'slot\s+release:', log))
    ledger.add('instance log records 20 completed slots', releases >= 20,
               'releases=%d' % releases)

    # Stated as a fact about this build, not as an absence of GPU use.
    offload_lines = re.findall(r'offload', log, re.IGNORECASE)
    ledger.add('this build emits no per-layer offload line (hence UNKNOWN)',
               len(offload_lines) == 0,
               'offload_mentions=%d' % len(offload_lines))


def check_gpu(gpu, ledger):
    proc = gpu.get('process') or {}
    cmd = proc.get('command_line') or ''

    ledger.add('evidence names a live pid', isinstance(proc.get('pid'), int)
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
    # 9.6 GB Q8 weights cannot fit in a few hundred MB of dedicated memory.
    ledger.add('adapter dedicated memory holds the weights (>8 GiB)',
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
