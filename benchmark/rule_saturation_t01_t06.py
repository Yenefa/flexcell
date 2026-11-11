#!/usr/bin/env python3
"""Measure whether a deterministic parser already solves T01-T06 at PLAN level.

WHAT THIS ANSWERS, AND WHAT IT DOES NOT
  Answers: of the 72 training instances, how many would a rule parser (given the same public
  observation the LLM gets) turn into the correct object-to-zone mapping and order?
  Does NOT answer: whether the robot then succeeds. A plan is not an execution, and this script
  never runs a simulator. The output is labelled PLAN-LAYER ONLY and must never be quoted as a
  success rate.

WHY IT MATTERS: if the parser matches the LLM plan-for-plan, the LLM adds nothing measurable on
these templates, and any claim of agent advantage has to come from tasks the parser fails. That is
a constraint on the project narrative, not a result about the robot.
"""
import json
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WT / 'runtime' / 'planner'))

import public_observation as po  # noqa: E402
import rule_planner_t01_t06 as rp  # noqa: E402


def expected_moves(spec):
    '''The answer, used HERE ONLY for scoring the parser. The parser never sees it.'''
    goal = spec.get('expected_goal') or {}
    return goal.get('placement') or {}


def score_one(spec):
    public = po.reduce_to_public(spec)
    observation = po.build_observation(public)
    moves, unmoved, why = rp.plan(observation)
    want = expected_moves(spec)
    # The parser names ZONES by measured side; the spec names them directly. Compare on the
    # mapping, ignoring order, because order is a separate clause.
    got = {}
    for mv in moves:
        got[mv['object']] = mv['zone']
    placement_ok = (got == want)
    # Relay order matters for T05/T06: the sequence of zones per object must match the spec's
    # visit requirement, not just the final landing.
    seq = {}
    for mv in moves:
        seq.setdefault(mv['object'], []).append(mv['zone'])
    visit = (spec.get('expected_goal') or {}).get('visit') or {}
    visit_ok = all(all(z in seq.get(n, []) for z in zs) for n, zs in visit.items())
    order_ok = True
    req = (spec.get('expected_goal') or {}).get('order') or []
    if req:
        order_ok = [m['object'] for m in moves if m['object'] in req] == list(req)
    unmoved_ok = set(unmoved) == set((spec.get('expected_goal') or {}).get('unmoved') or [])
    return {'task_id': spec['task_id'], 'template': spec['template_id'],
            'planned': bool(moves), 'why': why,
            'placement_ok': placement_ok, 'visit_ok': visit_ok,
            'order_ok': order_ok, 'unmoved_ok': unmoved_ok,
            'got': got, 'want': want}


def main():
    rows = [score_one(json.loads(p.read_text(encoding='utf-8')))
            for p in sorted((WT / 'benchmark' / 'tasks' / 'train').glob('*.json'))]
    by = {}
    for r in rows:
        b = by.setdefault(r['template'], [0, 0, 0])
        b[0] += 1
        b[1] += 1 if r['planned'] else 0
        b[2] += 1 if (r['planned'] and r['placement_ok'] and r['visit_ok']
                       and r['order_ok'] and r['unmoved_ok']) else 0
    print('PLAN-LAYER ONLY -- this is not an execution result and not a success rate')
    print('%-32s %8s %10s %10s' % ('template', 'n', 'planned', 'plan-correct'))
    for t, (n, p, c) in sorted(by.items()):
        print('%-32s %8d %10d %10d' % (t, n, p, c))
    n = len(rows)
    p = sum(1 for r in rows if r['planned'])
    c = sum(1 for r in rows if r['planned'] and r['placement_ok'] and r['visit_ok']
            and r['order_ok'] and r['unmoved_ok'])
    print('-' * 64)
    print('%-32s %8d %10d %10d' % ('TOTAL', n, p, c))
    out = WT / 'setup' / 'acceptance' / 'evobot_rule_saturation_t01_t06_20261111'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'plan_layer_results.json').write_text(
        json.dumps({'layer': 'PLAN ONLY', 'n': n, 'planned': p, 'plan_correct': c,
                    'by_template': by, 'rows': rows}, indent=2) + '\n', encoding='utf-8')
    print('wrote', (out / 'plan_layer_results.json').relative_to(WT))
    return 0


if __name__ == '__main__':
    sys.exit(main())
