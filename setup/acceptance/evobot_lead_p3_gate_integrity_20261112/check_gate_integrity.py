#!/usr/bin/env python3
"""Check whether P3's improvement chain is actually gated, and whether the freeze holds.

THREE CHECKS, each answering a question the project asserts an answer to
    1. does run_loop.py ask the regression gate to run the regressions?
    2. do all pinned files still match their recorded hashes?
    3. do all acceptance verifiers pass, and if not, which pre-existing failures make
       an all-green gate impossible?

WHY 3 MATTERS
    If four verifiers fail for reasons unrelated to any proposal, an all-green gate rejects
    everything. That is presumably why run_regressions=False was passed - which means the
    gate was disabled rather than made differential.
"""
import glob
import hashlib
import json
import os
import subprocess
import sys


def find_repo_root(start):
    cur = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(cur, 'benchmark', 'tasks')):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise SystemExit('REFUSED: repo root not found above %s' % start)
        cur = parent


REPO = find_repo_root(os.path.dirname(os.path.abspath(__file__)))
FREEZE = os.path.join(REPO, 'setup', 'acceptance', 'evobot_capability_freeze_20261111')
LOOP = os.path.join(REPO, 'evolution', 'proposals', 'run_loop.py')


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    print('=== 1. is the regression gate asked to run the regressions? ===')
    if not os.path.exists(LOOP):
        raise SystemExit('REFUSED: run_loop.py not found')
    text = open(LOOP, encoding='utf-8').read()
    disabled = 'run_regressions=False' in text
    print('  run_loop.py calls regress.gate(..., run_regressions=False):', disabled)
    print('  gate default is run_regressions=True, so the caller is opting out')
    if disabled:
        print('  -> the independent-verifier regression is NOT part of the loop.')
    print()

    print('=== 2. do the pinned files still match, in EVERY generation of the baseline? ===')
    print('    The project re-pins formally (see evobot_freeze_change_20261111), so a drift against a')
    print('    SUPERSEDED baseline is expected and is not a defect. Only the LIVE one matters.')
    print()
    generations = [
        ('oldest', 'setup/acceptance/evobot_capability_freeze_20261111/capability_baseline.json'),
        ('middle', 'setup/acceptance/evobot_freeze_change_20261111/capability_baseline.json'),
        ('LIVE  ', 'benchmark/capability_baseline.json'),
    ]
    for label, rel in generations:
        gp = os.path.join(REPO, rel)
        if not os.path.exists(gp):
            print('  %s  %s  MISSING' % (label, rel))
            continue
        gen = json.load(open(gp, encoding='utf-8'))
        pinned_gen = gen.get('pinned_files') or {}
        d = []
        for relf, expected in pinned_gen.items():
            fp = os.path.join(REPO, relf)
            if not os.path.exists(fp) or sha256_file(fp) != expected:
                d.append(relf)
        print('  %s  pinned=%d drifted=%d  %s' % (label, len(pinned_gen), len(d), rel))
        for relf in d:
            print('             DRIFT %s' % relf)
    print()
    baseline_path = os.path.join(FREEZE, 'capability_baseline.json')
    try:
        baseline = json.load(open(baseline_path, encoding='utf-8'))
    except Exception as exc:
        raise SystemExit('REFUSED: cannot read capability_baseline.json: %s' % exc)
    pinned = baseline.get('pinned_files') or {}
    drift = []
    for rel, expected in sorted(pinned.items()):
        path = os.path.join(REPO, rel)
        if not os.path.exists(path):
            drift.append((rel, 'MISSING'))
            continue
        actual = sha256_file(path)
        if actual != expected:
            drift.append((rel, actual))
    print('  pinned files: %d   drifted: %d' % (len(pinned), len(drift)))
    for rel, actual in drift:
        print('    DRIFT  %s' % rel)
        print('           expected %s' % (pinned.get(rel) or '')[:32])
        print('           actual   %s' % actual[:32])
    verdict = 'INTACT' if not drift else 'DRIFTED'
    print('  -> freeze verdict: %s' % verdict)
    on_disk = os.path.join(FREEZE, 'freeze_check.txt')
    if os.path.exists(on_disk):
        recorded = open(on_disk, encoding='utf-8').read().strip()
        print('  recorded on disk: %s' % recorded)
        if verdict == 'DRIFTED':
            print('  -> THE RECORDED CHECK IS STALE: it says intact while a pinned file has changed')
    print()

    print('=== 3. which verifiers fail for pre-existing reasons? ===')
    verifiers = sorted(glob.glob(os.path.join(REPO, 'setup', 'acceptance', '*', 'verify.py')))
    failing = []
    for v in verifiers:
        try:
            proc = subprocess.run([sys.executable, v], capture_output=True, text=True,
                                  timeout=180, cwd=os.path.dirname(v))
        except subprocess.TimeoutExpired:
            failing.append((os.path.basename(os.path.dirname(v)), 'TIMEOUT'))
            continue
        if proc.returncode != 0:
            lines = [l for l in (proc.stderr or proc.stdout or '').strip().splitlines() if l.strip()]
            failing.append((os.path.basename(os.path.dirname(v)), (lines[-1] if lines else '')[:100]))
    print('  verifiers: %d   failing: %d   passing: %d'
          % (len(verifiers), len(failing), len(verifiers) - len(failing)))
    for name, why in failing:
        print('    FAIL  %-44s %s' % (name, why))
    print()
    if failing:
        print('  -> an ALL-GREEN gate is impossible while these fail, which is why the loop')
        print('     disables the regression instead of making it differential.')
    else:
        print('  -> an all-green gate is possible now.')
    print()
    print('CONCLUSION')
    print('  Gate enabled        : %s' % (not disabled))
    print('  Freeze holds        : %s' % (verdict == 'INTACT'))
    print('  Pre-existing fails  : %d of %d verifiers' % (len(failing), len(verifiers)))
    print()
    print('  A gate that is off protects nothing, and a freeze record that disagrees with its')
    print('  own verifier is not evidence. Both are recorded rather than repaired here, because')
    print('  the pinned files are frozen and re-running the batches is a human decision.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
