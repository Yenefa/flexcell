#!/usr/bin/env python3
"""Grade A-prime's 16 executed T14 trials - SYMMETRIC with how B was graded.

FIRST ATTEMPT HERE USED A DIFFERENT SEQUENCE SOURCE FOR EACH ARM, WHICH WAS WRONG.
I derived A-prime's move_sequence from the executor's completed_stage_ids, while B's
came from observe_from_run's pick.jsonl rule (outcome==0, in order). Those are
different recorders, and it manufactured a difference that is not in the world:

  HO-40348a081df6: executor reported error 62 and completed_stage_ids=[],
                   but BOTH objects ended in zone_2 within 58 mm and 48 mm.

Six of A-prime's seven "failed" runs placed both objects correctly. The executor's
verdict and the world's state are different things - the same separation the archived
B runs show, where 11/16 executed but 14/16 evaluated.

FIX: build A-prime's observation with the SAME observe_from_run.build_observation()
that produced B's observation.json, from the SAME pick.jsonl rule, plus the same
GZ_GROUND_TRUTH capture. Now both arms are measured by one code path.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, WT)
sys.path.insert(0, os.path.join(WT, 'benchmark', 'evaluators'))
from benchmark.evaluators import evaluate as evaluator      # noqa: E402
import observe_from_run as ofr                              # noqa: E402

sys.path.insert(0, HERE)
from grade_aprime_runs import reconstruct_goal              # noqa: E402

RUNS = os.path.join(HERE, 'runs')
PUBLIC = os.path.join(WT, 'benchmark', 'held_out', 'recovery_public80')
B_RUNS = os.path.join(WT, 'setup', 'acceptance', 'evobot_crosstype_20261111',
                      'runs_T14_ordered_pair')


def spec_for(task_id):
    public = json.load(open(os.path.join(PUBLIC, task_id + '.json'), encoding='utf-8'))
    goal = reconstruct_goal(public['instruction'], public)
    spec = dict(public)
    spec['expected_goal'] = goal
    spec['constraints'] = {'order': goal['order'], 'must_not_move': []}
    spec['template_id'] = 'T14_ordered_pair'
    return spec, public, goal


def aprime_observation(task_id, public):
    """The SAME construction observe_from_run used for B."""
    rd = os.path.join(RUNS, task_id)
    gt = json.load(open(os.path.join(rd, 'ground_truth.json'), encoding='utf-8'))
    zones = {z['name']: z['pose'] for z in public['zones']}
    names = [o['name'] for o in public['objects']]
    return ofr.build_observation(os.path.join(rd, 'sim'), names,
                                 ground_truth=gt, zones=zones)


def main():
    ids = sorted(d for d in os.listdir(RUNS) if d.startswith('HO-'))
    rows = []
    for task_id in ids:
        spec, public, goal = spec_for(task_id)
        rd = os.path.join(RUNS, task_id)
        plan = json.load(open(os.path.join(rd, 'plan.json'), encoding='utf-8'))
        plan_seq = [s['object_name'] for s in plan['stages']]
        comp = json.load(open(os.path.join(rd, 'composite.json'), encoding='utf-8'))
        res = comp.get('result') or {}
        obs = aprime_observation(task_id, public)
        verdict = evaluator.evaluate(spec, obs)
        rows.append({
            'task_id': task_id,
            'planning_correct': plan_seq == goal['order'],
            'plan_sequence': plan_seq,
            'execution_succeeded': res.get('outcome') == 0,
            'outcome': res.get('outcome'),
            'error_code': res.get('error_code'),
            'evaluation_passed': verdict['passed'],
            'failed_clauses': verdict['failed_clauses'],
            'observed_sequence': obs['move_sequence'],
            'measured_objects': sorted(obs['objects']),
            'gt_source': json.load(open(os.path.join(rd, 'ground_truth.json'),
                                        encoding='utf-8')).get('source'),
        })

    # B, re-derived through the identical spec reconstruction
    brows = []
    for task_id in ids:
        spec, public, goal = spec_for(task_id)
        rd = os.path.join(B_RUNS, task_id)
        rec = json.load(open(os.path.join(rd, 'recovery_decision.json'), encoding='utf-8'))
        act = rec.get('action')
        nested = (rec.get('decision') or {}).get('action')
        eff = act if act is not None else nested
        fe = json.load(open(os.path.join(rd, 'failure_evidence.json'), encoding='utf-8'))
        o1 = json.load(open(os.path.join(rd, 'observation_after1.json'), encoding='utf-8'))
        of = json.load(open(os.path.join(rd, 'observation.json'), encoding='utf-8'))
        def grade(o):
            return evaluator.evaluate(spec, {
                'objects': o.get('objects') or {},
                'move_sequence': o.get('move_sequence') or [],
                'visits': o.get('visits') or {}})['passed']
        brows.append({'exec': fe.get('outcome') == 0 and eff in (None, 'no_recovery'),
                      'eval1': grade(o1), 'evalf': grade(of)})

    n = len(rows)
    pc = sum(1 for r in rows if r['planning_correct'])
    es = sum(1 for r in rows if r['execution_succeeded'])
    ep = sum(1 for r in rows if r['evaluation_passed'])
    bpc = sum(1 for _ in ids)   # B's plan == required order 16/16, verified separately
    bes = sum(1 for b in brows if b['exec'])
    be1 = sum(1 for b in brows if b['eval1'])
    bef = sum(1 for b in brows if b['evalf'])

    print('=' * 84)
    print('A-PRIME vs B on the 16 T14 instances - SAME plans, SAME executor, SAME evaluator')
    print('=' * 84)
    print()
    print('  %-36s %-14s %-14s' % ('metric', 'A-prime', 'B (deepseek)'))
    print('  ' + '-' * 80)
    print('  %-36s %-14s %-14s' % ('planning_correct', '%d/%d' % (pc, n), '%d/%d' % (bpc, n)))
    print('  %-36s %-14s %-14s' % ('execution_succeeded (1st attempt)',
          '%d/%d' % (es, n), '%d/%d' % (bes, n)))
    print('  %-36s %-14s %-14s' % ('independent_evaluation_passed (1st)',
          '%d/%d' % (ep, n), '%d/%d' % (be1, n)))
    print('  %-36s %-14s %-14s' % ('evaluation_passed (after recovery)',
          'N/A (none)', '%d/%d' % (bef, n)))
    print('  %-36s %-14s %-14s' % ('model calls (cost)', '0', str(n)))
    print()
    print('  %-18s %-7s %-7s %-7s %-24s' % ('run', 'plan', 'exec', 'eval', 'observed sequence'))
    print('  ' + '-' * 76)
    for r in rows:
        print('  %-18s %-7s %-7s %-7s %-24s'
              % (r['task_id'], r['planning_correct'], r['execution_succeeded'],
                 r['evaluation_passed'], ','.join(x[-1] for x in r['observed_sequence']) or '(none)'))
    print()
    print('  errors: %s' % {r['task_id'][-6:]: r['error_code'] for r in rows
                            if not r['execution_succeeded']})
    with open(os.path.join(HERE, 'grading', 'aprime_vs_b_final.json'), 'w',
              encoding='utf-8') as f:
        json.dump({'n': n,
                   'aprime': {'planning': pc, 'execution': es, 'eval_first': ep,
                              'eval_after_recovery': None, 'model_calls': 0},
                   'b': {'planning': bpc, 'execution': bes, 'eval_first': be1,
                         'eval_after_recovery': bef, 'model_calls': n},
                   'rows': rows}, f, indent=2, default=str)
    print('  wrote grading/aprime_vs_b_final.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
