#!/usr/bin/env python3
"""Baseline A-prime end-to-end: task -> observation -> RULE plan -> plan.json.

WHY THIS IS A SEPARATE ENTRY POINT AND NOT A FLAG ON run_baseline_b
  P0 requires an A-prime / B comparison under the SAME inputs and the SAME execution path. A flag
  would let the two diverge by accident -- a shared code path that branches once is exactly how an
  'identical conditions' claim quietly stops being true. This file imports run_baseline_b for
  read_task, to_executor_plan and the observation builder, and replaces exactly one thing: the
  planner. If it ever grows a second difference, the comparison is void.

WHAT A-PRIME IS
  A deterministic rule parser over the same public observation B sees: instruction, visible
  objects, visible bins. It does NOT read expected_goal, constraints, template_id, random_seed or
  any verdict. Baseline A from the original track read expected_goal and was therefore an
  open-book oracle, not a baseline.

COST: zero model calls. The whole point of this baseline is that it costs nothing, so if it
matches B, B's measurable value on these templates is zero.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'runtime' / 'planner'))

import public_observation as po  # noqa: E402
import rule_planner as rp  # noqa: E402
import run_baseline_b as rb  # noqa: E402


def run_one(task_path, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    raw_task = rb.read_task(task_path)
    # The reducer is what strips expected_goal. Applying it here means A-prime is structurally
    # incapable of seeing the answer, rather than merely refraining from looking.
    task_public = (po.reduce_to_public(raw_task)
                   if 'expected_goal' in raw_task else raw_task)
    observation = po.build_observation(task_public)
    (out / 'observation_input.json').write_text(
        json.dumps(observation, indent=2) + '\n', encoding='utf-8')

    moves, unmoved, why = rp.plan(observation)
    agent_plan = {'moves': moves, 'unmoved': unmoved}
    (out / 'rule_plan.json').write_text(json.dumps(
        {'agent_plan': agent_plan, 'why': why}, indent=2) + '\n', encoding='utf-8')

    result = {'task_id': task_public['task_id'], 'planned': bool(moves),
              'moves': len(moves), 'why': why, 'tokens': 0}
    if not moves:
        result['stage'] = 'no rule matched - declined'
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n',
                                          encoding='utf-8')
        return result

    plan = rb.to_executor_plan(task_public, observation, agent_plan)
    (out / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')
    result['stages'] = len(plan['stages'])
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('tasks', nargs='+')
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)
    rows = []
    for task_path in args.tasks:
        name = Path(task_path).stem
        rows.append(run_one(task_path, Path(args.out) / name))
        print(json.dumps(rows[-1], indent=2))
    planned = sum(1 for r in rows if r.get('planned'))
    print(json.dumps({'instances': len(rows), 'planned': planned,
                      'total_tokens': 0}, indent=2))
    return 0 if planned == len(rows) else 1


if __name__ == '__main__':
    sys.exit(main())
