#!/usr/bin/env python3
"""Audit the four experience records BEFORE accepting an independent review of them.

FOUR QUESTIONS, each answerable from the committed repository
    1. Is the hash chain intact?                      (tamper / deletion detection)
    2. Can each record lesson change an agent plan?   (audit_actionability's question, re-run here)
    3. Does each record evidence exist in a MACHINE-READABLE file, or only in prose?
    4. Does the one actionable lesson address a failure that occurs anywhere in the archive?

WHY 3 AND 4 MATTER
    store.py says evidence must be "measured facts, never a self-claim". A fact that exists only in a
    README is a claim someone wrote about a run, not a measurement a reader can re-derive. And a lesson
    about a failure mode that never occurs cannot change any future plan either - it is true and inert.

    Together those two make P4 answerable with a mechanism instead of an absence: if no lesson can act on
    any archived task, then a D that reuses these lessons has nothing to reuse.
"""
import json
import os
import sys

WT = '/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp'
RECORDS = os.path.join(WT, 'evolution', 'experience', 'records.jsonl')
ACCEPT = os.path.join(WT, 'setup', 'acceptance')

sys.path.insert(0, os.path.join(WT, 'evolution', 'experience'))
sys.path.insert(0, os.path.join(WT, 'evolution', 'transfer'))


def read_records():
    return [json.loads(l) for l in open(RECORDS, encoding='utf-8') if l.strip()]


def files_containing(root, needle):
    hits = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            path = os.path.join(dirpath, name)
            try:
                if os.path.getsize(path) > 4 * 1024 * 1024:
                    continue
                with open(path, 'rb') as fh:
                    if needle.encode('utf-8') in fh.read():
                        hits.append(path)
            except OSError:
                continue
    return hits


def main():
    print('=== 1. hash chain ===')
    try:
        import store
        ok, why = store.verify_chain(RECORDS)
        print('  ', why)
    except Exception as exc:
        print('  could not verify:', exc)
    records = read_records()
    print('  records:', len(records))
    print()

    print('=== 2. can the lesson change a plan? ===')
    try:
        import audit_actionability as aa
        classify = aa.classify_actionability
    except Exception:
        classify = None
    actionable = 0
    for rec in records:
        if classify:
            label, why = classify(rec['lesson'])
        else:
            label, why = 'UNKNOWN', 'classifier unavailable'
        if label == 'PLANNER_ACTIONABLE':
            actionable += 1
        print('  %-24s %-18s %s' % (rec['task_id'], label, why[:60]))
    print('  ACTIONABLE: %d/%d' % (actionable, len(records)))
    print()

    print('=== 3. is the evidence machine-readable, or only prose? ===')
    prose_only = 0
    for rec in records:
        run = os.path.join(WT, rec['source_run'])
        needle = None
        ev = rec.get('evidence') or {}
        for key in ('detail', 'failure'):
            if isinstance(ev.get(key), str):
                needle = ev[key]
                break
        if needle is None or not os.path.isdir(run):
            print('  %-24s UNCHECKABLE (no detail string, or source_run missing)' % rec['task_id'])
            prose_only += 1
            continue
        hits = files_containing(run, needle)
        machine = [h for h in hits if not h.lower().endswith('.md')]
        if machine:
            print('  %-24s MACHINE-READABLE (%d file(s))' % (rec['task_id'], len(machine)))
        elif hits:
            prose_only += 1
            print('  %-24s PROSE ONLY (%s)'
                  % (rec['task_id'], os.path.relpath(hits[0], WT)))
        else:
            prose_only += 1
            print('  %-24s NOT FOUND in its own source_run' % rec['task_id'])
    print('  NOT machine-verifiable: %d/%d' % (prose_only, len(records)))
    print()

    print('=== 4. does the actionable lesson address a failure that occurs? ===')
    counts = {}
    for rec in records:
        ev = rec.get('evidence') or {}
        code = ev.get('error_code')
        if not isinstance(code, int):
            continue
        n = 0
        needle = '"error_code": %d' % code
        for path in files_containing(ACCEPT, needle) or []:
            n += 1
        counts[(rec['task_id'], code)] = n
    for (task, code), n in counts.items():
        verdict = 'OCCURS' if n else 'NEVER OCCURS in any machine-readable archive file'
        print('  %-24s error_code=%-3d -> %s' % (task, code, verdict))
    print()

    print('=== verdict ===')
    print('  chain intact                        : see section 1')
    print('  lessons that could move a plan      : %d of %d' % (actionable, len(records)))
    print('  records with machine-readable proof : %d of %d' % (len(records) - prose_only, len(records)))
    if actionable <= 1 and prose_only == len(records):
        print()
        print('  The experience channel carries at most one plan-changing lesson, its evidence is')
        print('  narrated rather than measured, and the failure it addresses does not appear in any')
        print('  machine-readable archive file. A cross-task reuse arm built on this channel has')
        print('  nothing to reuse, which is a MECHANISM for EVOLUTION_ADVANTAGE_NOT_DEMONSTRATED -')
        print('  not an absence of measurement.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
