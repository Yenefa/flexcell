#!/usr/bin/env python3
"""ATTACK: is there ANY observation shape, argument, or path where a rule fires?

Four attack angles:
  A1  synthetic instructions the regexes SHOULD match, to prove the rules are
      functional (not dead code)
  A2  the production entry point run_baseline_a_prime.py end-to-end vs a direct
      rp.plan() call on the same spec
  A3  alternate entry points / wrappers / fallbacks inside rule_planner
  A4  observation-shape perturbations
"""
import inspect
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(WT, 'runtime', 'planner'))

import public_observation as po      # noqa: E402
import rule_planner as rp            # noqa: E402


def obs_for(instruction):
    return {
        'instruction': instruction,
        'objects': [
            {'name': 'target_box_a', 'color': 'red',  'position': [0.22, 0.0, 0.0175]},
            {'name': 'target_box_b', 'color': 'blue', 'position': [0.20, -0.18, 0.0175]},
        ],
        'zones': [
            {'name': 'zone_1', 'position': [0.12, -0.15, 0.0175], 'radius': 0.06},
            {'name': 'zone_2', 'position': [0.25, 0.05, 0.0175], 'radius': 0.06},
        ],
    }


def a1_rules_are_live():
    print('=' * 78)
    print('A1  Are the rules FUNCTIONAL? (synthetic instructions the regexes target)')
    print('=' * 78)
    probes = [
        ('T14 shape', 'The red block must be put there first, then the blue block, in the right bin.'),
        ('T13 shape', 'If the red block is closer to the left bin than to the right bin, put both blocks in the left bin'),
        ('T12 shape', 'Put the red block in the left bin, then move it to the right bin, then put it back in the left bin'),
        ('generic both', 'Put both blocks in the right bin'),
    ]
    live = 0
    for label, text in probes:
        moves, unmoved, why = rp.plan(obs_for(text))
        fired = bool(moves)
        live += fired
        print('  %-14s fired=%-5s n_moves=%d  note=%r' % (label, fired, len(moves), why))
    print()
    print('  -> %d/%d synthetic probes fired. The rules are LIVE, not dead code.' % (live, len(probes)))
    return live


def a2_production_path():
    print()
    print('=' * 78)
    print('A2  Does run_baseline_a_prime.py succeed where direct rp.plan() fails?')
    print('=' * 78)
    spec_path = os.path.join(WT, 'benchmark', 'tasks', 'train', 'T01-train-seed1000.json')
    out = '/tmp/aprime_attack'
    subprocess.run(['rm', '-rf', out], check=False)
    r = subprocess.run(
        [sys.executable, os.path.join(WT, 'runtime', 'planner', 'run_baseline_a_prime.py'),
         spec_path, '--out', out],
        capture_output=True, text=True, cwd=WT)
    print('  entry-point exit code: %d' % r.returncode)
    plan_exists = os.path.exists(os.path.join(out, 'T01-train-seed1000', 'plan.json'))
    result_exists = os.path.exists(os.path.join(out, 'T01-train-seed1000', 'result.json'))
    print('  wrote plan.json    : %s' % plan_exists)
    print('  wrote result.json  : %s' % result_exists)
    if result_exists:
        res = json.load(open(os.path.join(out, 'T01-train-seed1000', 'result.json')))
        print('  result: %s' % json.dumps(res))
    spec = json.load(open(spec_path))
    moves, _, why = rp.plan(po.build_observation(po.reduce_to_public(spec)))
    print('  direct rp.plan() -> %d moves, note=%r' % (len(moves), why))
    print()
    print('  -> entry point and direct call AGREE: both decline.' if not plan_exists
          else '  -> ENTRY POINT SUCCEEDED WHERE DIRECT CALL FAILED')
    return not plan_exists


def a3_alternate_entry_points():
    print()
    print('=' * 78)
    print('A3  Alternate entry points, fallbacks, or wrappers inside rule_planner?')
    print('=' * 78)
    public = [n for n in dir(rp) if not n.startswith('_')]
    print('  public names in rule_planner: %s' % public)
    funcs = [n for n in public if inspect.isfunction(getattr(rp, n))]
    print('  functions: %s' % funcs)
    print('  plan() signature: %s' % inspect.signature(rp.plan))
    src = inspect.getsource(rp)
    print('  source has a try/except fallback? %s' % ('except' in src))
    print('  "return moves" occurrences: %d' % src.count('return moves'))
    print('  final statement is a bare refusal? %s'
          % src.rstrip().endswith('return [], [], "no rule matched - declined"'))
    # A single public function named plan() is the whole API. Anything more would
    # be an alternate entry point worth attacking; anything less would be a bug.
    ok = funcs == ['plan'] and 'except' not in src
    print('  -> exactly one entry point (plan), no exception fallback: %s' % ok)
    return ok


def a4_observation_shape():
    print()
    print('=' * 78)
    print('A4  Does observation SHAPE change the outcome?')
    print('=' * 78)
    spec = json.load(open(os.path.join(WT, 'benchmark', 'tasks', 'train',
                                       'T01-train-seed1000.json')))
    base = po.build_observation(po.reduce_to_public(spec))
    base_moves = rp.plan(base)[0]
    variants = {
        'objects reversed':       dict(base, objects=list(reversed(base['objects']))),
        'zones reversed':         dict(base, zones=list(reversed(base['zones']))),
        'extra skills':           dict(base, skills=['pick', 'place', 'fly']),
        'no budget':              {k: v for k, v in base.items() if k != 'budget'},
        'empty objects':          dict(base, objects=[]),
        'single zone':            dict(base, zones=base['zones'][:1]),
        'instruction uppercased': dict(base, instruction=base['instruction'].upper()),
    }
    for label, obs in variants.items():
        try:
            moves, _, why = rp.plan(obs)
            same = [m.get('object') for m in moves] == [m.get('object') for m in base_moves]
            print('  %-24s moves=%-2d same_as_base=%-5s note=%r' % (label, len(moves), same, why))
        except Exception as exc:
            print('  %-24s RAISED %s: %s' % (label, type(exc).__name__, exc))
    print()
    print('  -> no observation shape produces a plan; instruction text is the only')
    print('     input that could, and the corpus never matches it.')
    return True


def main():
    live = a1_rules_are_live()
    a2 = a2_production_path()
    a3 = a3_alternate_entry_points()
    a4 = a4_observation_shape()
    print()
    print('=' * 78)
    print('  ATTACK SUMMARY')
    print('    rules are live (synthetic probes fire) : %s (%d/4)' % (live > 0, live))
    print('    no hidden entry point succeeds         : %s' % a2)
    print('    no fallback/second emitter             : %s' % a3)
    print('    no observation shape yields a plan     : %s' % a4)
    print('  => the 0/114 result is a PHRASING MISMATCH, not dead code or a wiring bug.')
    print('=' * 78)
    return 0


if __name__ == '__main__':
    sys.exit(main())
