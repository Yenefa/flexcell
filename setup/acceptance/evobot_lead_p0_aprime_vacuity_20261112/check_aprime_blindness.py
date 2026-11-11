#!/usr/bin/env python3
"""Is Baseline A-prime really blind to the answer, or only in the happy path?

WHY
    A-prime's whole claim to being a baseline rests on one sentence in its docstring: it 'does NOT
    read expected_goal, constraints, template_id, random_seed or any verdict'. If that is only true
    by convention rather than by construction, A-prime is an oracle with extra steps and every
    comparison against B is worthless -- which is exactly the defect that sank Baseline A.

WHAT IT CHECKS
    1. reduce_to_public() strips the answer-bearing keys from a real spec.
    2. Corrupting expected_goal cannot change the plan (the structural test, not a promise).
    3. The caller actually applies the reducer -- and whether it applies it UNCONDITIONALLY.

RESULT (2026-11-12): checks 1 and 2 PASS. Check 3 passes today but is conditional, which is a
latent hole recorded in README section 7 rather than silently fixed, because fixing it touches a
P0 entry point that other baselines share.
"""
import copy
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

    specs = sorted(glob.glob(os.path.join(REPO, 'benchmark', 'tasks', '*', '*.json')))
    if not specs:
        raise SystemExit('REFUSED: no task specs found')

    failures = []

    # --- 1. the reducer strips the answer ---------------------------------
    sample = json.load(open(specs[0]))
    if 'expected_goal' not in sample:
        raise SystemExit('REFUSED: sample spec has no expected_goal, so this test cannot prove'
                         ' anything about stripping it')
    reduced = po.reduce_to_public(sample)
    leaked = [k for k in ('expected_goal', 'constraints', 'template_id', 'random_seed',
                          'verdict') if k in reduced]
    print('1. reducer strips answer keys: %s' % ('PASS' if not leaked else 'FAIL %s' % leaked))
    if leaked:
        failures.append('reducer leaks %s' % leaked)

    # --- 2. corruption cannot change the plan -----------------------------
    observation = po.build_observation(reduced)
    baseline_plan = rp.plan(copy.deepcopy(observation))
    corruptions = [{'x': 1}, None, 'GARBAGE',
                    {'moves': [{'object': 'target_box_b', 'zone': 'zone_1'}]}]
    stable = True
    for corrupt in corruptions:
        mutated = copy.deepcopy(sample)
        mutated['expected_goal'] = corrupt
        plan = rp.plan(po.build_observation(po.reduce_to_public(mutated)))
        if plan != baseline_plan:
            stable = False
            failures.append('plan changed under expected_goal=%r' % (corrupt,))
    print('2. plan invariant under expected_goal corruption: %s'
          % ('PASS' if stable else 'FAIL'))

    # --- 3. is the reducer applied unconditionally? -----------------------
    entry = os.path.join(REPO, 'runtime', 'planner', 'run_baseline_a_prime.py')
    source = open(entry, encoding='utf-8').read()
    conditional = "if 'expected_goal' in raw_task else raw_task" in source
    no_goal = sum(1 for p in specs
                  if 'expected_goal' not in json.load(open(p)))
    print('3. reducer applied unconditionally: %s'
          % ('PASS' if not conditional else
             'CONDITIONAL (currently harmless: %d of %d specs lack expected_goal)'
             % (no_goal, len(specs))))
    if conditional and no_goal:
        failures.append('conditional reducer AND specs without expected_goal exist')

    print()
    if failures:
        print('A_PRIME_NOT_BLIND')
        for f in failures:
            print('  ' + f)
        return 1
    print('A_PRIME_ANSWER_BLIND')
    if conditional:
        print('  (with a latent hole: the reducer is conditional. Harmless today because every')
        print('   spec carries expected_goal, but a spec without it would pass through')
        print('   unfiltered, carrying template_id and constraints.)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
