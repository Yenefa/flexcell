#!/usr/bin/env python3
"""INDEPENDENT reproduction of the "Baseline A-prime plans 0 of 72" claim.

Written from scratch for task-11. Does NOT import the Lead's scanner
(setup/acceptance/evobot_lead_p0_aprime_vacuity_20261112/scan_aprime_coverage.py).
The only shared code is the production path itself: public_observation + rule_planner,
which is what we are both measuring and therefore must be common.

Method: enumerate every task spec on disk, reduce each to its public observation,
call the real planner, and record plan-vs-refusal per template. Then, separately,
record WHICH rule (if any) matched, by instrumenting each regex in isolation.
"""
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(WT, 'runtime', 'planner'))

import public_observation as po          # noqa: E402
import rule_planner as rp                # noqa: E402

# The seven patterns, transcribed from rule_planner.py for ISOLATED probing.
# Each is compiled here independently so I can ask 'does THIS regex match?'
# without the earlier rules short-circuiting the function.
PATTERNS = {
    'T14_first':      r'the (\w+) block must be put there first',
    'T13_conditional': r'if the (\w+) block is closer to the (left|right) bin than to the '
                       r'(left|right) bin,\s*put both blocks in the (left|right) bin',
    'T12_relay':      r'put the (\w+) block in the (\w+) bin,\s*then move it to the '
                       r'(\w+) bin,\s*then put it back in the (\w+) bin',
    'generic_both':   r'put both blocks in the (\w+) bin',
    # fragments consumed INSIDE the rules above - probed to show they cannot
    # fire on their own (they are not standalone rules in the planner)
    'frag_in_the_bin': r'in the (\w+) bin',
    'frag_then_the':   r'then the (\w+) block',
    'frag_closer':     r'closer to the (left|right) bin',
}


def find_specs():
    """Every task spec on disk, by directory."""
    root = os.path.join(WT, 'benchmark', 'tasks')
    out = []
    for split in sorted(os.listdir(root)):
        d = os.path.join(root, split)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if name.endswith('.json'):
                out.append((split, name[:-5], os.path.join(d, name)))
    return out


def plan_one(path):
    """Run the production path exactly as run_baseline_a_prime.py does."""
    spec = json.load(open(path, encoding='utf-8'))
    public = po.reduce_to_public(spec) if 'expected_goal' in spec else spec
    obs = po.build_observation(public)
    moves, unmoved, why = rp.plan(obs)
    return spec, obs, moves, unmoved, why


def main():
    specs = find_specs()
    print('=' * 78)
    print('INDEPENDENT A-prime coverage census')
    print('=' * 78)
    print('  task specs found: %d' % len(specs))

    by_template = collections.defaultdict(lambda: {'n': 0, 'planned': 0,
                                                   'instr': set(), 'why': set()})
    rows = []
    for split, task, path in specs:
        spec, obs, moves, unmoved, why = plan_one(path)
        t = spec.get('template_id', '?')
        rec = by_template[t]
        rec['n'] += 1
        rec['planned'] += 1 if moves else 0
        rec['instr'].add(spec['instruction'])
        rec['why'].add(why)
        rows.append((split, task, t, bool(moves), len(moves), why,
                     spec['instruction']))

    print()
    print('  %-34s %5s %8s  %s' % ('template', 'n', 'planned', 'planner note'))
    print('  ' + '-' * 74)
    total = planned = 0
    for t in sorted(by_template):
        r = by_template[t]
        total += r['n']
        planned += r['planned']
        print('  %-34s %5d %8d  %s'
              % (t, r['n'], r['planned'], '; '.join(sorted(r['why']))))
    print('  ' + '-' * 74)
    print('  %-34s %5d %8d' % ('TOTAL', total, planned))
    print()
    print('  VERDICT: A-prime plans %d of %d specs (%.1f%%)'
          % (planned, total, 100.0 * planned / max(total, 1)))

    # ---- per-pattern isolated probe -------------------------------------
    print()
    print('=' * 78)
    print('  WHICH PATTERN COULD EVER MATCH? (isolated, per distinct instruction)')
    print('=' * 78)
    distinct = sorted({r[6] for r in rows})
    print('  distinct instructions across the corpus: %d' % len(distinct))
    print()
    for instr in distinct:
        hits = [name for name, pat in PATTERNS.items()
                if re.search(pat, instr, re.I)]
        print('  %r' % instr[:96])
        print('     -> patterns matching: %s' % (hits or 'NONE'))

    # ---- dump rows for the report ----------------------------------------
    outdir = os.path.join(HERE, 'census')
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, 'coverage_rows.tsv'), 'w',
              encoding='utf-8', newline='\n') as f:
        f.write('split\ttask\ttemplate\tplanned\tn_moves\twhy\tinstruction\n')
        for r in rows:
            f.write('\t'.join(str(x).replace('\t', ' ') for x in r) + '\n')
    print()
    print('  wrote census/coverage_rows.tsv (%d rows)' % len(rows))
    return 0 if planned == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
