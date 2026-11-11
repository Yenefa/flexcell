#!/usr/bin/env python3
"""Tests for gate_differential: it must reject NEW failures and only new ones.

WHY THE TESTS USE A SUBSET
    The real gate runs all 109 acceptance verifiers (~5 min). These tests run against two or three
    throwaway verify.py files so the COMPARISON LOGIC is exercised quickly and deterministically.
    The full-suite behaviour is covered by the loop run, not by these tests.
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evolution' / 'validation'))
import gate_differential as G  # noqa: E402


def make_verifier(dirpath, name, passes):
    d = Path(dirpath) / name
    d.mkdir(parents=True, exist_ok=True)
    body = 'import sys\nsys.exit(%d)\n' % (0 if passes else 1)
    p = d / 'verify.py'
    p.write_text(body, encoding='utf-8')
    return p


def proposal(**over):
    base = {'files': ['src/flexcell/nothing.py'],
            'evidence': {'detail': 'measured', 'error_code': 25},
            'expected_effect': 'x falls to 0',
            'rollback': 'revert'}
    base.update(over)
    return base


def known_set(names):
    return {'record_kind': 'EVOBOT_KNOWN_VERIFIER_FAILURES', 'failures':
            [{'verifier': n, 'reported': 'baselined for test'} for n in names]}


def run():
    results = []
    tmp = tempfile.mkdtemp(prefix='gate_')
    real_known = G.KNOWN
    try:
        ok_v = make_verifier(tmp, 'passes_always', True)
        bad_v = make_verifier(tmp, 'fails_always', False)
        known_path = Path(tmp) / 'known_failures.json'
        G.KNOWN = known_path

        # 1. baseline lists the failing verifier -> accepted, zero new
        known_path.write_text(json.dumps(known_set(['fails_always'])), encoding='utf-8')
        acc, why = G.gate(proposal(), verifiers=[ok_v, bad_v])
        results.append(('baselined failure unchanged -> ACCEPT', acc is True, why))

        # 2. a new failure appears -> rejected
        known_path.write_text(json.dumps(known_set([])), encoding='utf-8')
        acc, why = G.gate(proposal(), verifiers=[ok_v, bad_v])
        results.append(('new failure -> REJECT', acc is False and 'NEW' in why, why))

        # 3. a BASELINED verifier that now passes -> accepted and reported as an improvement.
        #    The baselined verifier must actually be RUN for this to mean anything; running a
        #    different verifier and expecting a 'cleared' note was my first version of this test
        #    and it was the test that was wrong, not the gate.
        was_failing = make_verifier(tmp, 'was_failing', True)
        known_path.write_text(json.dumps(known_set(['was_failing'])), encoding='utf-8')
        acc, why = G.gate(proposal(), verifiers=[was_failing])
        results.append(('baselined verifier now clears -> ACCEPT + noted',
                        acc is True and 'CLEARED' in why, why))

        # 4. missing baseline -> fail closed
        known_path.unlink()
        acc, why = G.gate(proposal(), verifiers=[ok_v])
        results.append(('missing baseline -> REJECT (fail closed)', acc is False, why))

        # 5. structural refusal still applies (protected path)
        known_path.write_text(json.dumps(known_set([])), encoding='utf-8')
        acc, why = G.gate(proposal(files=['benchmark/evaluators/evaluate.py']), verifiers=[ok_v])
        results.append(('protected path -> REJECT', acc is False and 'protected' in why.lower(), why))

        # 6. no verifiers -> refuse rather than accept untested
        acc, why = G.gate(proposal(), verifiers=[])
        results.append(('no verifiers -> REJECT', acc is False, why))

        # 7. a file the run rewrites is put back. Git cannot be used here (this worktree's .git
        #    holds a Windows path), so the restore is byte-snapshot based - and my first version
        #    used git and silently did nothing.
        mutated = Path(tmp) / 'evidence.json'
        mutated.write_text('original', encoding='utf-8')
        snap = {str(mutated): (hashlib.sha256(b'original').hexdigest(), b'original')}
        mutated.write_text('rewritten by a verifier', encoding='utf-8')
        now = {str(mutated): (hashlib.sha256(mutated.read_bytes()).hexdigest(),
                             mutated.read_bytes())}
        restored = G.restore_side_effects(snap, now)
        results.append(('verifier side effect -> file restored',
                        len(restored) == 1 and mutated.read_text() == 'original',
                        'restored=%d content=%r' % (len(restored), mutated.read_text())))
    finally:
        G.KNOWN = real_known
        shutil.rmtree(tmp, ignore_errors=True)

    print('%-52s %s' % ('test', 'result'))
    print('-' * 92)
    failed = 0
    for name, ok, why in results:
        print('%-52s %s' % (name, 'PASS' if ok else 'FAIL'))
        if not ok:
            failed += 1
            print('    reason was: %s' % why)
    print()
    print('%d/%d tests passed' % (len(results) - failed, len(results)))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(run())
