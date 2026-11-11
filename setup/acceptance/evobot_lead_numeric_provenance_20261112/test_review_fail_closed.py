#!/usr/bin/env python3
"""Prove review is FAIL-CLOSED: no verdict means no retrieval, not merely "not rejected"."""
import json
import os
import shutil
import sys
import tempfile

WT = '/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp'
for p in ('evolution/experience', 'experiments/baselines'):
    sys.path.insert(0, WT + '/' + p)
import store  # noqa: E402
import baseline_c as C  # noqa: E402

OBS = {'instruction': 'Put both blocks in the right bin.', 'objects': [], 'zones': [], 'skills': []}


def run():
    tmp = tempfile.mkdtemp(prefix='rev_')
    results = []
    try:
        store_path = os.path.join(tmp, 'records.jsonl')
        ev = {'detail': 'declared destination occupied at target_box_b-1', 'error_code': 60}
        rec = store.make_record('T-test', 'planning', ev,
                                'Order the moves so a later stage is not blocked by an earlier object.',
                                'setup/acceptance/x', 'failed')
        rec['provenance_verified'] = True
        rec['evidence_files'] = ['f']
        rec['record_sha256'] = store._hash({k: v for k, v in rec.items() if k != 'record_sha256'})
        store.append(store_path, rec)
        sha = rec['record_sha256']
        ledger = os.path.join(tmp, 'review_ledger.jsonl')

        # 1. no ledger at all -> nothing is approved
        got = C.retrieve(OBS, store_path)
        results.append(('no review ledger -> NOT retrieved', len(got) == 0, '%d lesson(s)' % len(got)))

        # 2. an ACCEPT verdict -> retrieved
        open(ledger, 'w').write(json.dumps({'record_sha256': sha, 'verdict': 'ACCEPT'}) + chr(10))
        got = C.retrieve(OBS, store_path)
        results.append(('independent ACCEPT -> retrieved', len(got) == 1, '%d lesson(s)' % len(got)))

        # 3. a REJECT verdict -> not retrieved
        open(ledger, 'w').write(json.dumps({'record_sha256': sha, 'verdict': 'REJECT'}) + chr(10))
        got = C.retrieve(OBS, store_path)
        results.append(('independent REJECT -> NOT retrieved', len(got) == 0, '%d lesson(s)' % len(got)))

        # 4. a verdict for a DIFFERENT record must not approve this one
        open(ledger, 'w').write(json.dumps({'record_sha256': '0' * 64, 'verdict': 'ACCEPT'}) + chr(10))
        got = C.retrieve(OBS, store_path)
        results.append(('ACCEPT for another digest -> NOT retrieved', len(got) == 0, '%d lesson(s)' % len(got)))

        # 5. a corrupted ledger must not fail OPEN
        open(ledger, 'w').write('{not json' + chr(10))
        got = C.retrieve(OBS, store_path)
        results.append(('corrupt ledger -> NOT retrieved (fail closed)', len(got) == 0, '%d lesson(s)' % len(got)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    failed = 0
    for name, ok, why in results:
        print('%-52s %-5s %s' % (name, 'PASS' if ok else 'FAIL', why))
        if not ok:
            failed += 1
    print()
    print('%d/%d tests passed' % (len(results) - failed, len(results)))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(run())
