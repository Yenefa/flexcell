#!/usr/bin/env python3
"""CRITICAL TEST: T12/T13/T14 templates EXIST as generators.

The Lead's claim says the rules were written for templates that do not exist here.
That is only true of benchmark/tasks/. This asks the materially different question:
do the rules WORK on the templates they were written for?
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(WT, 'runtime', 'planner'))
sys.path.insert(0, os.path.join(WT, 'benchmark', 'generators'))

import public_observation as po      # noqa: E402
import rule_planner as rp            # noqa: E402
import unseen_tasks as U             # noqa: E402


def public_from_generated(spec):
    public = {k: spec[k] for k in po.PUBLIC_KEYS if k in spec}
    return po.build_observation(public)


def main():
    print('=' * 78)
    print('Do the A-prime rules work on the templates they were WRITTEN for?')
    print('=' * 78)
    print('  These templates exist as generators in benchmark/generators/unseen_tasks.py,')
    print('  even though no spec of theirs is present in benchmark/tasks/.')
    print()
    print('  %-30s %6s %8s  %s' % ('template', 'n', 'planned', 'notes'))
    print('  ' + '-' * 72)

    grand = {}
    for template in sorted(U.TEMPLATES):
        planned = 0
        notes = set()
        n = 0
        for seed in range(7000, 7012):
            spec = U.generate(template, seed)
            obs = public_from_generated(spec)
            moves, unmoved, why = rp.plan(obs)
            n += 1
            planned += 1 if moves else 0
            notes.add(why)
        grand[template] = (n, planned, notes)
        print('  %-30s %6d %8d  %s' % (template, n, planned, '; '.join(sorted(notes))))
    print('  ' + '-' * 72)
    tot_n = sum(v[0] for v in grand.values())
    tot_p = sum(v[1] for v in grand.values())
    print('  %-30s %6d %8d' % ('TOTAL', tot_n, tot_p))
    print()
    if tot_p == tot_n:
        print('  *** ALL generated T12/T13/T14 instances ARE planned. ***')
        print('  => The rules are not broken. They are correct for the templates they')
        print('     target, and the benchmark split contains none of those templates.')
    else:
        print('  => %d/%d planned: rules partially match their own templates.' % (tot_p, tot_n))

    print()
    print('=' * 78)
    print('  Lineage check: rule_planner_pre_t14 (T12+T13 only) on the same corpus')
    print('=' * 78)
    import rule_planner_pre_t14 as pre
    for template in sorted(U.TEMPLATES):
        planned = 0
        n = 0
        for seed in range(7000, 7012):
            spec = U.generate(template, seed)
            obs = public_from_generated(spec)
            moves, _, _ = pre.plan(obs)
            n += 1
            planned += 1 if moves else 0
        print('  %-30s %6d %8d' % (template, n, planned))
    return 0


if __name__ == '__main__':
    sys.exit(main())
