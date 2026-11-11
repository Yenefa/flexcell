#!/usr/bin/env python3
"""Validate the PENDING place-release fix offline, and check its stated safety argument.

THE SAFETY ARGUMENT UNDER TEST
    The proposal says: "The evaluator grades the world, not the skill's self-report. Reclassifying the
    self-report cannot make a failing world pass."

    That is FALSE AS WRITTEN. benchmark/evaluators/observe_from_run.py lines 74 and 114 read
    place.released:

        if name and pose and row.get("released", True):

    That module BUILDS the observation the evaluator grades. So the field the fix changes IS read on
    the grading path. The argument needs checking, not accepting.

WHAT I FOUND
    The fix happens to be safe - but for an INCIDENTAL reason, not the stated one. All 51 place rows
    with released=False carry NO box_after, so flipping released alone changes nothing (the row is
    still skipped, because pose is None). The proposal separately PREDICTS that box_after will start
    being recorded - and that part DOES change the evaluator's input for all 51 rows.

    So the fix must be understood as two parts with different risk, and the proposal bundles them under
    one safety argument that only covers the first.
"""
import glob
import json
import os
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
ACCEPTANCE = os.path.join(REPO, 'setup', 'acceptance')
OBSERVE = os.path.join(REPO, 'benchmark', 'evaluators', 'observe_from_run.py')


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path, encoding='utf-8', errors='replace'):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def main():
    if not os.path.exists(OBSERVE):
        raise SystemExit('REFUSED: observe_from_run.py not found - the coupling claim cannot be tested')
    source = open(OBSERVE, encoding='utf-8').read()
    coupling = 'row.get("released"' in source
    print('=== 1. is the changed field on the grading path? ===')
    print('  observe_from_run.py reads place.released :', coupling)
    if coupling:
        print('  -> the proposal\'s anti-gaming rationale ("the evaluator grades the world, not the')
        print('     self-report") DOES NOT HOLD AS WRITTEN: the observation builder reads the')
        print('     self-report. Its safety must be established, not assumed.')
    print()

    skills_dirs = sorted({os.path.dirname(p) for p in
                          glob.glob(os.path.join(ACCEPTANCE, '**', 'skills', 'place.jsonl'),
                                    recursive=True)})
    if not skills_dirs:
        raise SystemExit('REFUSED: no archived place logs')
    denied = 0
    denied_with_box_after = 0
    released_with_box_after = 0
    for sd in skills_dirs:
        for row in read_jsonl(os.path.join(sd, 'place.jsonl')):
            if row.get('released') is False:
                denied += 1
                if row.get('box_after'):
                    denied_with_box_after += 1
            elif row.get('released') is True and row.get('box_after'):
                released_with_box_after += 1
    print('=== 2. why the fix is safe anyway - and it is incidental ===')
    print('  place rows with released=False          : %d' % denied)
    print('  ...that carry box_after                 : %d' % denied_with_box_after)
    print('  place rows with released=True AND box_after: %d' % released_with_box_after)
    print()
    if denied and denied_with_box_after == 0:
        print('  PART 1 (flip released only): SAFE, but incidentally. box_after is absent on every')
        print('  denied row, so observe_from_run still skips it (pose is None) and the observation is')
        print('  unchanged. Nothing in the design guarantees this - it is a property of the current')
        print('  failure path not writing box_after.')
    elif denied_with_box_after:
        print('  PART 1 IS NOT SAFE: %d denied rows DO carry box_after, so flipping released would'
              % denied_with_box_after)
        print('  feed place.box_after into the graded observation.')
    print()
    print('  PART 2 (also start recording box_after - which the proposal predicts) DOES change the')
    print('  grading input for all %d rows: they would move from verify.jsonl provenance to' % denied)
    print('  place.box_after. That is a real change to the observation, and it is not covered by the')
    print('  proposal\'s safety argument.')
    print()
    print('=== 3. would part 2 create false success? ===')
    print('  Not established offline. box_after does not exist for these rows, so its future value')
    print('  cannot be read from the archive - it would be whatever the patched skill measures at')
    print('  release time. For the 11 runs whose object never left its start pose, that pose is not in')
    print('  the destination, so a false success is UNLIKELY but NOT DEMONSTRATED.')
    print('  This must be checked on a real run after approval, not asserted here.')
    print()
    print('CONCLUSION')
    print('  The proposal\'s mechanism is right and the field it needs already exists. Its SAFETY')
    print('  ARGUMENT is incomplete: the observation builder reads place.released, so the fix is on the')
    print('  grading path. Part 1 is safe only because box_after is absent on denied rows; part 2')
    print('  changes the grading input for %d rows and needs its own regression check.' % denied)
    return 0


if __name__ == '__main__':
    sys.exit(main())
