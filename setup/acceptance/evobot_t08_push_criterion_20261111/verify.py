#!/usr/bin/env python3
"""Verifier for the T08 push clause: prove it can FAIL, and that it is a pure addition.

WHY THIS FILE EXISTS
  The push clause was added to the evaluator, the one component that decides what success
  means. A clause nobody has seen fail is not a criterion, it is decoration. This verifier
  drives the clause with synthetic final states whose correct verdict is known by construction,
  and it re-grades a spec with no push clause to prove the addition changed nothing there.

MUTATIONS (each must make at least one check red):
  keep     remove the min_displacement bound -> the 'never moved' case must stop failing
  lift     remove the vertical bound         -> the 'carried it' case must stop failing
  cos      remove the direction bound        -> the 'wrong direction' case must stop failing
  version  claim 0.2.0                       -> the version check must fail
"""
import json
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(WT / 'benchmark' / 'evaluators'))
import evaluate as ev  # noqa: E402

SPEC = {
    'task_id': 'T08-push-test',
    'template_id': 'T08_push',
    'objects': [
        {'name': 'target_box_a', 'initial_pose': [0.22, 0.0, 0.0175]},
        {'name': 'target_box_b', 'initial_pose': [0.20, -0.18, 0.0175]},
    ],
    'zones': [{'name': 'zone_push', 'pose': [0.16, 0.0, 0.0175], 'radius': 0.06}],
    'expected_goal': {
        'push': {
            'target_box_a': {
                'min_displacement_m': 0.030,
                'max_displacement_m': 0.150,
                'max_vertical_m': 0.020,
                'direction': [-1.0, 0.0],
                'min_direction_cosine': 0.9,
                'zone': 'zone_push',
            }
        }
    },
}


def verdict(after, **goal_over):
    spec = json.loads(json.dumps(SPEC))
    spec['expected_goal']['push']['target_box_a'].update(goal_over)
    state = {'objects': {'target_box_a': after,
                         'target_box_b': [0.20, -0.18, 0.0175]}}
    return ev.evaluate(spec, state)


def push_clause(v):
    for c in v['clauses']:
        if c['clause'].startswith('push:'):
            return c
    return None


CHECKS = []


def check(name):
    def deco(fn):
        CHECKS.append((name, fn))
        return fn
    return deco


@check('C1 the MEASURED 23 mm push FAILS the 30 mm criterion, and a real 40 mm push passes')
def _c1():
    # This is the whole point of the clause being honest. Step 0 measured 23.02 mm and was
    # ruled NOT_FEASIBLE against a 30 mm threshold frozen before the run. The criterion must
    # reproduce that: 23 mm FAILS. If this check ever passes a 23 mm push, the threshold was
    # quietly relaxed to make the result look better.
    c = push_clause(verdict([0.22 - 0.02302, -0.00192, 0.0175]))
    assert c and not c['ok'], c
    e = c['evidence']
    assert abs(e['displacement_m'] - 0.02302) < 1e-4, e
    assert e['displacement_m'] < e['min_displacement_m'], e
    # and the same direction at 40 mm does pass, so the clause is not simply always-false
    c2 = push_clause(verdict([0.22 - 0.040, 0.0, 0.0175]))
    assert c2 and c2['ok'], c2


@check('C2 an object that never moved fails, and the reason is displacement')
def _c2():
    c = push_clause(verdict([0.22, 0.0, 0.0175]))
    assert c and not c['ok'], c
    e = c['evidence']
    assert e['displacement_m'] < e['min_displacement_m'], e


@check('C3 carrying the object fails: displacement alone must not satisfy a push')
def _c3():
    c = push_clause(verdict([0.22 - 0.060, 0.0, 0.0175 + 0.060]))
    assert c and not c['ok'], c
    e = c['evidence']
    assert e['vertical_m'] > e['max_vertical_m'], e


@check('C4 pushing the wrong direction fails even at the right distance')
def _c4():
    c = push_clause(verdict([0.22 + 0.040, 0.0, 0.0175]))
    assert c and not c['ok'], c
    assert c['evidence']['direction_cosine'] < 0.9, c['evidence']


@check('C4b distance inside bounds but direction off by ~35 deg fails on the cosine alone')
def _c4b():
    # 0.040 m mostly along -x but with a large lateral component: displacement is in range,
    # vertical is zero, the zone is not required, so ONLY the cosine can reject it. Without
    # this case the cosine bound is untested and the 'cos' mutation stays green.
    import math
    ang = math.radians(35.0)
    dx, dy = -0.040 * math.cos(ang), 0.040 * math.sin(ang)
    c = push_clause(verdict([0.22 + dx, dy, 0.0175]))
    e = c['evidence']
    assert e['min_displacement_m'] <= e['displacement_m'] <= e['max_displacement_m'], e
    assert e['vertical_m'] <= e['max_vertical_m'], e
    assert e['direction_cosine'] < e['min_direction_cosine'], e
    assert not c['ok'], c


@check('C5 over-pushing past the upper bound fails')
def _c5():
    c = push_clause(verdict([0.22 - 0.200, 0.0, 0.0175]))
    assert c and not c['ok'], c
    e = c['evidence']
    assert e['displacement_m'] > e['max_displacement_m'], e


@check('C6 a missing object fails instead of crashing')
def _c6():
    v = ev.evaluate(json.loads(json.dumps(SPEC)),
                    {'objects': {'target_box_b': [0.20, -0.18, 0.0175]}})
    c = push_clause(v)
    assert c and not c['ok'] and c['evidence'].get('reason') == 'object missing', c


@check('C7 pure addition: a spec without a push clause grades as before')
def _c7():
    spec = json.loads(json.dumps(SPEC))
    del spec['expected_goal']['push']
    spec['expected_goal']['placement'] = {'target_box_a': 'zone_push'}
    state = {'objects': {'target_box_a': [0.16, 0.0, 0.0175],
                         'target_box_b': [0.20, -0.18, 0.0175]}}
    v = ev.evaluate(spec, state)
    names = [c['clause'] for c in v['clauses']]
    assert not any(n.startswith('push:') for n in names), names
    assert v['passed'] is True, v


@check('C8 the evaluator version was bumped when the criterion changed')
def _c8():
    assert ev.EVALUATOR_VERSION == '0.3.0', ev.EVALUATOR_VERSION


def run():
    fails = 0
    for name, fn in CHECKS:
        try:
            fn()
            print('  PASS ' + name)
        except AssertionError as exc:
            print('  FAIL ' + name + '  :: ' + str(exc)[:120])
            fails += 1
    return fails


def apply_mutation(kind):
    orig = ev.evaluate
    overrides = {'keep': ('min_displacement_m', 0.0),
                 'lift': ('max_vertical_m', 99.0),
                 'cos': ('min_direction_cosine', -2.0)}
    if kind in overrides:
        key, val = overrides[kind]

        def patched(spec, state, _k=key, _v=val):
            spec = json.loads(json.dumps(spec))
            for w in (spec['expected_goal'].get('push') or {}).values():
                w[_k] = _v
            return orig(spec, state)

        ev.evaluate = patched
    elif kind == 'version':
        ev.EVALUATOR_VERSION = '0.2.0'


def main(argv):
    if '--mutate' in argv:
        kind = argv[argv.index('--mutate') + 1]
        apply_mutation(kind)
        print('applied mutation: ' + kind)
        fails = run()
        print('  -> %d failing check(s)' % fails)
        return 1 if fails else 0
    print('== push clause verifier ==')
    fails = run()
    print('  -> %d passed, %d failed' % (len(CHECKS) - fails, fails))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))