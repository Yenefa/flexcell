#!/usr/bin/env python3
"""Tests for verify_provenance: it must accept real evidence and reject narration.

WHY THESE CASES
    The defect it guards against was not a crash - it was silence read as success. So the tests focus on
    the cases where a naive check passes: evidence that exists only in a README, evidence that is all
    numbers, and a source directory that exists but does not contain what the record claims.
"""
import os
import sys
import tempfile
import shutil

WT = '/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp'
sys.path.insert(0, os.path.join(WT, 'evolution', 'experience'))
import verify_provenance as vp


def run():
    results = []
    tmp = tempfile.mkdtemp(prefix='prov_')
    try:
        ev = {'detail': 'declared destination occupied', 'error_code': 60}

        # 1. evidence in a machine-readable file -> accept
        d1 = os.path.join(tmp, 'real')
        os.makedirs(os.path.join(d1, 'runs', 'a1'))
        open(os.path.join(d1, 'runs', 'a1', 'result.json'), 'w').write(
            '{"detail": "declared destination occupied", "error_code": 60}')
        ok, files, why = vp.verify_provenance(d1, ev)
        results.append(('evidence in a JSON log -> ACCEPT', ok is True, why))

        # 2. evidence ONLY in a README -> reject (this is the actual defect)
        d2 = os.path.join(tmp, 'prose')
        os.makedirs(os.path.join(d2, 'runs'))
        open(os.path.join(d2, 'README.md'), 'w').write('declared destination occupied')
        ok, files, why = vp.verify_provenance(d2, ev)
        results.append(('evidence only in README -> REJECT', ok is False, why))

        # 3. source_run missing -> reject (fail closed)
        ok, files, why = vp.verify_provenance(os.path.join(tmp, 'nope'), ev)
        results.append(('source_run missing -> REJECT', ok is False, why))

        # 4. evidence is all numbers -> reject: nothing is checkable
        ok, files, why = vp.verify_provenance(d1, {'error_code': 60})
        results.append(('evidence has no verifiable string -> REJECT', ok is False, why))

        # 5. partial: one string found, one missing -> reject
        ok, files, why = vp.verify_provenance(d1, {'detail': 'declared destination occupied',
                                                  'failure': 'a string that is not there'})
        results.append(('one evidence string missing -> REJECT', ok is False, why))

        # 6. a planner-level lesson passes the actionability guard
        ok, why = vp.check_actionability('Declare exactly the objects present in the world.', WT)
        results.append(('planner lesson -> ACCEPT', ok is True, why))

        # 7. a harness lesson is refused at write time (R3's failure)
        ok, why = vp.check_actionability(
            'Give each stacked run a valid distinct domain id; reusing one domain exhausts participant slots.', WT)
        results.append(('harness lesson -> REJECT', ok is False, why))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print('%-52s %s' % ('test', 'result'))
    print('-' * 96)
    failed = 0
    for name, ok, why in results:
        print('%-52s %s' % (name, 'PASS' if ok else 'FAIL'))
        if not ok:
            failed += 1
            print('    got: %s' % why)
    print()
    print('%d/%d tests passed' % (len(results) - failed, len(results)))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(run())
