#!/usr/bin/env python3
"""Adversarial self-test for verify_clef_receipt.py.

Each case copies the archive into a throwaway tree, applies one tamper, and
requires the verifier to reject it.  A checker that cannot be made to fail is
decoration, not evidence.

Note on the last group: the tamper is applied *to the receipt*, not to the
machine.  This proves the verifier notices a doctored archive.  It does not and
cannot prove anything about a live GPU; that is what the log and module
evidence are for, and why `gpu_execution` stays UNKNOWN.

Exit 0 = every case behaved as declared.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

ARCHIVE = 'setup/acceptance/clef_recorded_001_20261024'
PILOT = 'setup/acceptance/q8_pilot_20261005/episodes'


def build_tree(tmp):
    """Recreate the minimal subtree the verifier resolves its paths in."""
    dest = tmp / ARCHIVE
    dest.mkdir(parents=True)
    for name in ('clef_20261024T131429Z.json', 'llama-server-instance.log',
                 'gpu_evidence.json', 'verify_clef_receipt.py'):
        shutil.copy2(HERE / name, dest / name)
    # The verifier re-hashes the three source episodes, so they must exist
    # at the same relative paths under the fake root.
    (tmp / PILOT).mkdir(parents=True)
    for raw in (ROOT / PILOT).glob('*.raw'):
        shutil.copy2(raw, tmp / PILOT / raw.name)
    return dest


def run(archive):
    proc = subprocess.run(
        [sys.executable, str(archive / 'verify_clef_receipt.py')],
        capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def edit_json(path, mutate):
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)
    mutate(data)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def edit_log(path, mutate):
    text = path.read_text(encoding='utf-8')
    path.write_text(mutate(text), encoding='utf-8')


def case_report_status(archive):
    edit_json(archive / 'clef_20261024T131429Z.json',
              lambda d: d.__setitem__('status', 'FAIL'))


def case_drop_a_row(archive):
    edit_json(archive / 'clef_20261024T131429Z.json',
              lambda d: d['rows'].pop())


def case_flip_a_row_to_failed(archive):
    def mutate(d):
        d['rows'][3]['pass'] = False
        d['rows'][3]['errors'] = ['synthetic']
    edit_json(archive / 'clef_20261024T131429Z.json', mutate)


def case_wrong_weight_sha(archive):
    edit_json(archive / 'clef_20261024T131429Z.json',
              lambda d: d.__setitem__('local_weight_sha256', '0' * 64))


def case_claim_gpu_verified_without_log(archive):
    edit_json(archive / 'clef_20261024T131429Z.json',
              lambda d: d.__setitem__('gpu_execution', 'VERIFIED_ON_GPU'))


def case_claim_served_identity(archive):
    edit_json(archive / 'clef_20261024T131429Z.json',
              lambda d: d.__setitem__('served_weight_identity', 'MATCH'))


def case_server_says_other_model(archive):
    def mutate(d):
        payload = json.loads(d['rows'][0]['response_json'])
        payload['model'] = 'D:\\other\\Different-Model-Q4.gguf'
        d['rows'][0]['response_json'] = json.dumps(payload)
    edit_json(archive / 'clef_20261024T131429Z.json', mutate)


def case_unnormalised_probabilities(archive):
    def mutate(d):
        payload = json.loads(d['rows'][0]['response_json'])
        payload['answers']['next_action']['probabilities']['PICK'] = 0.5
        d['rows'][0]['response_json'] = json.dumps(payload)
    edit_json(archive / 'clef_20261024T131429Z.json', mutate)


def case_robot_commands_claimed(archive):
    edit_json(archive / 'clef_20261024T131429Z.json',
              lambda d: d.__setitem__('robot_commands_sent', 12))


def case_episode_sha_forged(archive):
    def mutate(d):
        d['rows'][0]['episode_sha256'] = 'f' * 64
    edit_json(archive / 'clef_20261024T131429Z.json', mutate)


def case_log_missing_listen_line(archive):
    edit_log(archive / 'llama-server-instance.log',
             lambda t: t.replace('listening on http://127.0.0.1:11435', ''))


def case_log_too_few_slots(archive):
    def mutate(text):
        lines = [ln for ln in text.splitlines(True) if 'slot      release:' not in ln]
        return ''.join(lines)
    edit_log(archive / 'llama-server-instance.log', mutate)


def case_no_vulkan_module(archive):
    def mutate(d):
        d['loaded_gpu_modules'] = [m for m in d['loaded_gpu_modules']
                                   if 'vulkan' not in m.lower()]
    edit_json(archive / 'gpu_evidence.json', mutate)


def case_small_dedicated_memory(archive):
    edit_json(archive / 'gpu_evidence.json',
              lambda d: d['gpu'].__setitem__('dedicated_usage_bytes', 512 * 1024 * 1024))


def case_no_ngl_flag(archive):
    def mutate(d):
        cmd = d['process']['command_line'].replace('-ngl 99', '-ngl 0')
        d['process']['command_line'] = cmd
    edit_json(archive / 'gpu_evidence.json', mutate)


CASES = [
    ('A clean archive verifies', None, 0),
    ('B status downgraded', case_report_status, 1),
    ('C one row deleted', case_drop_a_row, 1),
    ('D a row flipped to failed', case_flip_a_row_to_failed, 1),
    ('E weight sha replaced', case_wrong_weight_sha, 1),
    ('F GPU claimed verified with no log line', case_claim_gpu_verified_without_log, 1),
    ('G served identity claimed as MATCH', case_claim_served_identity, 1),
    ('H server reports a different model', case_server_says_other_model, 1),
    ('I probabilities not normalised', case_unnormalised_probabilities, 1),
    ('J robot commands claimed', case_robot_commands_claimed, 1),
    ('K episode sha forged', case_episode_sha_forged, 1),
    ('L listen line stripped from log', case_log_missing_listen_line, 1),
    ('M all slot releases removed', case_log_too_few_slots, 1),
    ('N Vulkan module dropped from evidence', case_no_vulkan_module, 1),
    ('O dedicated memory shrunk to 512 MiB', case_small_dedicated_memory, 1),
    ('P -ngl 99 replaced on the command line', case_no_ngl_flag, 1),
]


def main():
    failures = 0
    for name, tamper, want in CASES:
        with tempfile.TemporaryDirectory() as tmpname:
            tmp = Path(tmpname)
            archive = build_tree(tmp)
            if tamper is not None:
                tamper(archive)
            code, output = run(archive)
            ok = (code == want)
            if not ok:
                failures += 1
            print('%-46s %s  (exit=%d, want %d)'
                  % (name, 'PASS' if ok else 'FAIL', code, want))
            if not ok:
                print(output)
    print()
    if failures:
        print('SELFTEST: %d of %d cases did not behave as declared'
              % (failures, len(CASES)))
        return 1
    print('SELFTEST: %d/%d cases behave as declared' % (len(CASES), len(CASES)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
