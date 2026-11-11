#!/usr/bin/env python3
"""A regression gate that can actually be ON: reject NEW failures, not existing ones.

WHY THIS EXISTS
    regress.gate(proposal, run_regressions=True) requires every verifier under setup/acceptance/
    to pass. Four of the 109 do not, for reasons unrelated to any proposal (recorded in
    known_failures.json). So an all-green gate rejects every proposal forever - which is why
    run_loop.py called it with run_regressions=False, i.e. the gate has never gated anything.

WHAT THIS DOES DIFFERENTLY
    1. Structural checks: delegates to regress.gate with run_regressions=False, so the pinned
       module is reused read-only and never modified.
    2. Differential regression: runs the verifiers and compares the FAILING SET against
       known_failures.json. A new failure REJECTS. A baselined failure that now clears is an
       improvement and is reported as such.
    3. Fail closed: a missing or unreadable known_failures.json REJECTS, because a missing
       baseline must not become a free pass.

    THE SIDE EFFECT PROBLEM. 108 of the 109 verify.py write their own verify_result.json, so
    running the suite MODIFIES the archive it is checking. This module snapshots which files
    were already dirty, then restores whatever the run itself dirtied, so gating a proposal
    cannot rewrite evidence.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACCEPTANCE = ROOT / 'setup' / 'acceptance'
KNOWN = ROOT / 'evolution' / 'validation' / 'known_failures.json'

sys.path.insert(0, str(ROOT / 'evolution' / 'validation'))
import regress  # noqa: E402  (pinned; imported read-only, never modified)


# GIT CANNOT BE USED HERE. This worktree's .git file holds a Windows absolute path, so `git`
# fails from inside WSL ('fatal: not a git repository') - and my first implementation of this
# module used git anyway, which meant the restore silently did nothing while reporting success.
# Snapshotting bytes works regardless of where the gate runs.
SNAPSHOT_SUFFIXES = ('.json', '.txt')
SNAPSHOT_MAX_BYTES = 2 * 1024 * 1024


def _snapshot():
    """path -> (sha256, bytes) for the files a verifier run rewrites.

    SCOPE: one level inside each directory that holds a verify.py. Verifiers write their result
    beside themselves, not into the archived runs/ subtrees - so a recursive walk would scan
    thousands of files the run cannot touch, and did: the unrestricted version made six unit
    tests take over two minutes.
    """
    snap = {}
    if not ACCEPTANCE.exists():
        return snap
    for verifier in ACCEPTANCE.glob('*/verify.py'):
        for path in verifier.parent.iterdir():
            if not path.is_file() or path.suffix not in SNAPSHOT_SUFFIXES:
                continue
            try:
                data = path.read_bytes()
            except OSError:
                continue
            if len(data) > SNAPSHOT_MAX_BYTES:
                continue
            snap[str(path)] = (hashlib.sha256(data).hexdigest(), data)
    return snap


def restore_side_effects(before, after):
    """Put back any archive file the verifier run rewrote. Returns the restored paths."""
    restored = []
    for path, (digest, data) in before.items():
        now = after.get(path)
        if now is not None and now[0] == digest:
            continue
        try:
            Path(path).write_bytes(data)
            restored.append(path)
        except OSError:
            pass
    return restored


def load_known():
    if not KNOWN.exists():
        return None
    try:
        doc = json.loads(KNOWN.read_text(encoding='utf-8'))
    except Exception:
        return None
    return {f['verifier'] for f in doc.get('failures') or []}


def run_verifiers(verifiers):
    failing = set()
    for v in verifiers:
        try:
            proc = subprocess.run([sys.executable, str(v)], capture_output=True, text=True,
                                  timeout=300, cwd=str(v.parent))
        except subprocess.TimeoutExpired:
            failing.add(v.parent.name)
            continue
        if proc.returncode != 0:
            failing.add(v.parent.name)
    return failing


def gate(proposal, run_regressions=True, verifiers=None):
    ok, why = regress.gate(proposal, run_regressions=False)
    if not ok:
        return False, why

    known = load_known()
    if known is None:
        return False, 'known_failures.json missing or unreadable; refusing rather than treating nothing as baselined'
    if not run_regressions:
        return True, 'structure accepted (regressions skipped by caller); ' + why

    vlist = verifiers if verifiers is not None else sorted(ACCEPTANCE.glob('*/verify.py'))
    if not vlist:
        return False, 'no verifiers found; refusing rather than accepting untested'

    before = _snapshot()
    failing = run_verifiers(vlist)
    restored = restore_side_effects(before, _snapshot())

    ran = {v.parent.name for v in vlist}
    new = sorted(failing - known)
    cleared = sorted((known & ran) - failing)
    note = ''
    if restored:
        note = ' [restored %d archive file(s) the verifier run rewrote]' % len(restored)
    if new:
        return False, ('NEW verifier failures not in the baseline (%d): %s'
                       % (len(new), ', '.join(new[:5]))) + note

    msg = ('structure ok; %d verifier(s) run; %d known failure(s) unchanged; 0 new'
           % (len(vlist), len(failing & known)))
    if cleared:
        msg += '; baseline now CLEARED (improvement): ' + ', '.join(cleared[:5])
    return True, msg + note


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('usage: gate_differential.py <proposal.json>')
        raise SystemExit(2)
    prop = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    accepted, reason = gate(prop)
    print(('ACCEPTED' if accepted else 'REJECTED') + ': ' + reason)
    raise SystemExit(0 if accepted else 1)
