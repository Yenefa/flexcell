#!/usr/bin/env python3
""""Status check for the offline proposal generator (issue #236)."

WHY THIS EXISTS
    generate.py decides whether to emit a proposal by counting occurrences of a failure
    signature. It never asks whether that proposal has already been shown to be wrong.

    That is not hypothetical. actuator_stall_preregistration.json carries a
    superseded_basis recording that its premise was measured and refuted, and
    release_confirmation_preregistration.json names it in supersedes with the reason.
    generate.py reads neither, so it will happily re-emit a proposal the repository has
    already documented as unsound.

THE FOUR STATES, and they are not the same thing:
    ACTIVE      - a live record with no negative basis. Generate.
    INVALIDATED - the record says its basis was found wrong. Do NOT generate; say why.
    SUPERSEDED  - another record names this one as replaced. Do NOT generate; name who.
    UNKNOWN     - no record at all. GENERATE, but label it UNKNOWN and unverified.

    UNKNOWN is deliberately NOT treated as approved or verified. The #236 acceptance
    criterion says a missing status must not become validated by default, so a proposal
    that was never reviewed is emitted with proposal_status UNKNOWN and an explicit note.

WHAT THIS DOES NOT DO
    It reads no code, runs no robot, judges no proposal's merit, and changes no approval
    state. It reads the JSON records sitting next to the proposals and reports them.
"""
import json
import os

ACTIVE = 'ACTIVE'
INVALIDATED = 'INVALIDATED'
SUPERSEDED = 'SUPERSEDED'
UNKNOWN = 'UNKNOWN'

NEGATIVE_KEYS = ('superseded_basis', 'invalidated_basis', 'refuted_basis')


def _load_json(path):
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _why(record):
    if isinstance(record, str):
        return record
    if isinstance(record, dict):
        for k in ('why', 'reason', 'detail', 'note'):
            if record.get(k):
                return str(record[k])
        return json.dumps(record)[:200]
    return str(record)


def load_status_index(proposals_dir):
    index = {}
    try:
        names = sorted(os.listdir(proposals_dir))
    except OSError:
        return index

    for name in names:
        if not name.endswith('.json'):
            continue
        rec = _load_json(os.path.join(proposals_dir, name))
        if not isinstance(rec, dict):
            continue
        sig = rec.get('signature') or rec.get('proposal') or rec.get('proposal_id')
        if isinstance(sig, str):
            sig = sig.strip()
        for key in NEGATIVE_KEYS:
            if key in rec and rec[key]:
                target = sig or name[:-5].replace('_preregistration', '')
                index[target] = {
                    'status': INVALIDATED,
                    'reason': '%s in %s: %s' % (key, name, _why(rec[key])),
                    'source': name,
                }
        if sig and sig not in index:
            index[sig] = {
                'status': ACTIVE,
                'reason': 'record present in %s' % name,
                'source': name,
            }

    for name in names:
        if not name.endswith('.json'):
            continue
        rec = _load_json(os.path.join(proposals_dir, name))
        if not isinstance(rec, dict):
            continue
        sup = rec.get('supersedes')
        if not sup:
            continue
        text = _why(sup)
        parts = text.split()
        if not parts:
            continue
        target = parts[0].strip('/,')
        if not target:
            continue
        if index.get(target, {}).get('status') != INVALIDATED:
            index[target] = {
                'status': SUPERSEDED,
                'reason': 'superseded by %s: %s' % (name, text[:200]),
                'source': name,
            }
    return index


def check(signature, index):
    entry = index.get(signature)
    if not entry:
        note = 'no status record for %s; emitting as UNKNOWN, not approved or verified' % signature
        return True, UNKNOWN, note
    status = entry['status']
    if status in (INVALIDATED, SUPERSEDED):
        return False, status, entry['reason']
    return True, status, entry['reason']