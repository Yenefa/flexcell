#!/usr/bin/env python3
"""Does Baseline A-prime plan anything at all? Runs the real planner over every task spec.

WHY
    Every archived a_prime.json on disk records a refusal. Before concluding that P0's A-prime arm
    is empty, that has to be re-derived from the live planner over the full spec set rather than
    inferred from 20 old artifacts.

    It is empty. 0 of 72. The rules implement T12 and T14, which are not in this benchmark, and
    none of T01-T06, which are. See README.md.

REFUSES rather than reporting success if it finds no specs, so a wrong path cannot look clean.
"""
import collections
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
sys.path.insert(0, os.path.join(REPO, 'runtime', 'planner'))


def main():
    import public_observation as po
    import rule_planner as rp

    files = sorted(glob.glob(os.path.join(REPO, 'benchmark', 'tasks', 'train', '*.json')))
    if not files:
        raise SystemExit('REFUSED: no task specs found under benchmark/tasks/train')

    by_template = collections.defaultdict(lambda: [0, 0])
    notes = collections.Counter()
    for path in files:
        spec = json.load(open(path))
        template = spec.get('template_id', '?')
        public = po.reduce_to_public(spec) if 'expected_goal' in spec else spec
        observation = po.build_observation(public)
        result = rp.plan(observation)
        if isinstance(result, tuple) and len(result) == 3:
            moves, _unmoved, note = result
        else:
            moves, note = [], '(unexpected return shape)'
        planned = bool(moves)
        by_template[template][0 if planned else 1] += 1
        if not planned:
            notes[note or '(no note)'] += 1

    print('%-34s %8s %8s' % ('template', 'planned', 'refused'))
    print('-' * 54)
    total_p = total_r = 0
    for template, (planned, refused) in sorted(by_template.items()):
        print('%-34s %8d %8d' % (template, planned, refused))
        total_p += planned
        total_r += refused
    print('-' * 54)
    print('%-34s %8d %8d' % ('TOTAL', total_p, total_r))
    print()
    if notes:
        print('refusal notes:')
        for note, count in notes.most_common():
            print('  x%-3d %s' % (count, note))
        print()
    if total_p == 0:
        print('A_PRIME_VACUOUS: the planner produced no plan for any task.')
        print('P0 has no A-prime arm; a comparison against it is not a measurement.')
        return 0
    print('A_PRIME_PLANS %d of %d' % (total_p, total_p + total_r))
    return 0


if __name__ == '__main__':
    sys.exit(main())
