#!/usr/bin/env python3
"""Are the A-prime plans on T12/T13/T14 CORRECT, not merely emitted?

Planned != correct. A rule can emit moves that name the wrong zones or the wrong
order. This scores each generated instance against its own expected_goal, and
separates the two questions the coverage census conflates.
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


def score(moves, goal):
    """Mirror the project's own scoring: placement mapping + order + visit."""
    if not moves:
        return False, 'no moves'
    got = {m['object']: m['zone'] for m in moves}
    want = goal.get('placement') or {}
    if not all(got.get(k) == v for k, v in want.items()):
        return False, 'placement wrong: got %r want %r' % (got, want)
    order = goal.get('order') or []
    if order:
        seq = [m['object'] for m in moves]
        if seq[:len(order)] != order:
            return False, 'order wrong: got %r want %r' % (seq[:len(order)], order)
    vs = goal.get('visit_sequence') or {}
    for name, req in vs.items():
        seq = [m['zone'] for m in moves if m['object'] == name]
        if seq != list(req):
            return False, 'visit_sequence wrong: got %r want %r' % (seq, req)
    visit = goal.get('visit') or {}
    for name, req in visit.items():
        seq = [m['zone'] for m in moves if m['object'] == name]
        if not all(z in seq for z in req):
            return False, 'visit missing: got %r need %r' % (seq, req)
    return True, 'ok'


def run(planner, label):
    print('  %s' % label)
    print('  %-30s %6s %8s %8s' % ('template', 'n', 'planned', 'correct'))
    print('  ' + '-' * 58)
    tn = tp = tc = 0
    reasons = []
    for template in sorted(U.TEMPLATES):
        n = planned = correct = 0
        for seed in range(7000, 7012):
            spec = U.generate(template, seed)
            public = {k: spec[k] for k in po.PUBLIC_KEYS if k in spec}
            obs = po.build_observation(public)
            moves, _, _ = planner.plan(obs)
            ok, why = score(moves, spec['expected_goal'])
            n += 1
            planned += 1 if moves else 0
            correct += 1 if ok else 0
            if moves and not ok:
                reasons.append((template, seed, why))
        tn += n; tp += planned; tc += correct
        print('  %-30s %6d %8d %8d' % (template, n, planned, correct))
    print('  ' + '-' * 58)
    print('  %-30s %6d %8d %8d' % ('TOTAL', tn, tp, tc))
    for r in reasons[:4]:
        print('      e.g. %s seed %d: %s' % r)
    print()
    return tn, tp, tc


def main():
    print('=' * 78)
    print('PLANNED vs CORRECT on the templates the rules target')
    print('=' * 78)
    print()
    run(rp, 'rule_planner.py (full rule set)')
    import rule_planner_pre_t14 as pre
    run(pre, 'rule_planner_pre_t14.py (T12+T13 only, no T14 branch)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
