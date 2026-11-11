#!/usr/bin/env python3
"""Build A-prime executor plans for the 16 T14 ids - OFFLINE, no simulator.

FAIRNESS CONDITION 3 (same executor path) is satisfied structurally, not by
intention: this calls the SAME `run_baseline_b.to_executor_plan()` that produced
B's plan.json. Only the planner differs, exactly as run_baseline_a_prime.py
intends. If this script re-implemented the conversion, the comparison would be
measuring two conversions rather than two planners.

Produces runs/<id>/plan.json + observation_input.json, ready for the executor.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(WT, 'runtime', 'planner'))
sys.path.insert(0, WT)

import public_observation as po        # noqa: E402
import rule_planner as rp              # noqa: E402
import run_baseline_b as rb            # noqa: E402

PUBLIC = os.path.join(WT, 'benchmark', 'held_out', 'recovery_public80')
B_RUNS = os.path.join(WT, 'setup', 'acceptance', 'evobot_crosstype_20261111',
                      'runs_T14_ordered_pair')
OUT = os.path.join(HERE, 'runs')


def main():
    ids = sorted(os.listdir(B_RUNS))
    os.makedirs(OUT, exist_ok=True)
    print('=' * 78)
    print('A-prime executor plans for %d T14 instances (offline)' % len(ids))
    print('=' * 78)
    rows = []
    for task_id in ids:
        pub_path = os.path.join(PUBLIC, task_id + '.json')
        if not os.path.exists(pub_path):
            print('  %-18s NO PUBLIC SPEC' % task_id)
            rows.append({'task_id': task_id, 'planned': False,
                         'reason': 'public spec missing'})
            continue
        task_public = json.load(open(pub_path, encoding='utf-8'))
        observation = po.build_observation(task_public)

        # A-prime plans from the SAME observation B consumed. Verify that.
        b_obs_path = os.path.join(B_RUNS, task_id, 'observation_input.json')
        b_obs = json.load(open(b_obs_path, encoding='utf-8'))
        same_obs = (observation['instruction'] == b_obs['instruction']
                    and [o['name'] for o in observation['objects']]
                        == [o['name'] for o in b_obs['objects']]
                    and [z['name'] for z in observation['zones']]
                        == [z['name'] for z in b_obs['zones']])

        moves, unmoved, note = rp.plan(observation)
        d = {'task_id': task_id, 'planned': bool(moves), 'note': note,
             'same_observation_as_B': same_obs,
             'aprime_moves': moves}

        if not moves:
            print('  %-18s DECLINED (%s)' % (task_id, note))
            rows.append(d)
            continue

        agent_plan = {'moves': moves, 'unmoved': unmoved}
        # THE SAME conversion B used - condition 3
        plan = rb.to_executor_plan(task_public, observation, agent_plan)
        outdir = os.path.join(OUT, task_id)
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, 'plan.json'), 'w', encoding='utf-8') as f:
            json.dump(plan, f, indent=2)
        with open(os.path.join(outdir, 'observation_input.json'), 'w',
                  encoding='utf-8') as f:
            json.dump(observation, f, indent=2)

        b_plan = json.load(open(os.path.join(B_RUNS, task_id, 'plan.json'),
                                encoding='utf-8'))
        b_seq = [s['object_name'] for s in b_plan.get('stages') or []]
        a_seq = [s['object_name'] for s in plan['stages']]
        d.update({'same_observation_as_B': same_obs,
                  'aprime_sequence': a_seq, 'b_sequence': b_seq,
                  'same_order_as_B': a_seq == b_seq,
                  'stages': len(plan['stages']),
                  'clearance_m': plan['clearance_m'],
                  'motion_profile_id': plan['motion_profile_id'],
                  'position_tolerance_m': plan['position_tolerance_m']})
        print('  %-18s planned  order=%-9s same_as_B=%-5s obs_match=%s'
              % (task_id, ','.join(x[-1] for x in a_seq), a_seq == b_seq, same_obs))
        rows.append(d)

    n = len(rows)
    planned = sum(1 for r in rows if r.get('planned'))
    same_obs = sum(1 for r in rows if r.get('same_observation_as_B'))
    same_ord = sum(1 for r in rows if r.get('same_order_as_B'))
    print()
    print('  planned             : %d/%d' % (planned, n))
    print('  same observation    : %d/%d  (fairness condition 2)' % (same_obs, n))
    print('  same order as B     : %d/%d' % (same_ord, n))
    with open(os.path.join(HERE, 'grading', 'aprime_plans.json'), 'w',
              encoding='utf-8') as f:
        json.dump(rows, f, indent=2, default=str)
    print('  wrote runs/<id>/plan.json and grading/aprime_plans.json')
    return 0 if planned == n else 1


if __name__ == '__main__':
    sys.exit(main())
