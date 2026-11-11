#!/usr/bin/env python3
"""Grade A-prime's 16 executed T14 trials with the FROZEN evaluator, and put the
four numbers next to B's in the same shape.

SOURCES (all measured, none claimed):
  end state     runs/<id>/ground_truth.json  (GZ_GROUND_TRUTH, captured before teardown)
  move order    runs/<id>/composite.json completed_stage_ids  (the executor's own
                record of which stages completed, in order)
  executor      benchmark/tools/run_composite_plan.py -> RunComposite 'run_composite'
  answer        reconstructed from the public instruction, validated 16/16 against
                the archive's own recorded order clause (see README section 1)
  evaluator     benchmark/evaluators/evaluate.py v0.5.0, unmodified

THE FOUR NUMBERS, per arm, never folded:
  planning_correct              the PLAN names the right objects in the right order
  execution_succeeded           outcome==0 on the FIRST attempt, no recovery
  independent_evaluation_passed frozen evaluator on the measured end state
  evaluation_passed_after_recovery  (A-prime has no recovery; recorded as N/A)
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, WT)
from benchmark.evaluators import evaluate as evaluator   # noqa: E402

RUNS = os.path.join(HERE, 'runs')
PUBLIC = os.path.join(WT, 'benchmark', 'held_out', 'recovery_public80')
B_RUNS = os.path.join(WT, 'setup', 'acceptance', 'evobot_crosstype_20261111',
                      'runs_T14_ordered_pair')


def reconstruct_goal(instruction, public):
    m = re.search(r'put both blocks in the (\w+) bin', instruction, re.I)
    if not m:
        return None
    side = m.group(1).lower()
    zones = {z['name']: z['pose'] for z in public['zones']}
    by_side = sorted(zones, key=lambda n: zones[n][1], reverse=True)
    zone = by_side[0] if side.startswith('l') else by_side[1]
    m_first = re.search(r'the (\w+) block must be put there first', instruction, re.I)
    if not m_first:
        return None
    c2n = {str(o.get('color', '')).lower(): o['name'] for o in public['objects']}
    first = c2n.get(m_first.group(1).lower())
    m_then = re.search(r'then the (\w+) block', instruction, re.I)
    second = c2n.get(m_then.group(1).lower()) if m_then else None
    if not (first and second):
        return None
    return {'placement': {first: zone, second: zone},
            'order': [first, second], 'unmoved': []}


def order_from_stage_ids(stage_ids):
    """turn ['target_box_b-0','target_box_a-1'] -> ['target_box_b','target_box_a']."""
    out = []
    for sid in stage_ids or []:
        name = sid.rsplit('-', 1)[0]
        if name not in out:
            out.append(name)
    return out


def main():
    ids = sorted(d for d in os.listdir(RUNS) if d.startswith('HO-'))
    rows = []
    for task_id in ids:
        d = {'task_id': task_id}
        rd = os.path.join(RUNS, task_id)
        public = json.load(open(os.path.join(PUBLIC, task_id + '.json'),
                                encoding='utf-8'))
        goal = reconstruct_goal(public['instruction'], public)
        spec = dict(public)
        spec['expected_goal'] = goal
        spec['constraints'] = {'order': goal['order'], 'must_not_move': []}
        spec['template_id'] = 'T14_ordered_pair'

        # --- planning_correct (from the plan A-prime built offline)
        plan = json.load(open(os.path.join(rd, 'plan.json'), encoding='utf-8'))
        plan_seq = [s['object_name'] for s in plan['stages']]
        zones = {z['name']: z['pose'] for z in public['zones']}
        plan_ok = plan_seq == goal['order']
        for obj, zn in goal['placement'].items():
            hit = [s for s in plan['stages'] if s['object_name'] == obj]
            if not hit or (abs(hit[0]['place_pose'][0] - zones[zn][0]) > 0.06
                           or abs(hit[0]['place_pose'][1] - zones[zn][1]) > 0.06):
                plan_ok = False
        d['planning_correct'] = plan_ok
        d['plan_sequence'] = plan_seq
        d['required_order'] = goal['order']

        # --- execution (executor's own record)
        comp_path = os.path.join(rd, 'composite.json')
        if os.path.exists(comp_path):
            comp = json.load(open(comp_path, encoding='utf-8'))
            res = comp.get('result') or {}
            d['outcome'] = res.get('outcome')
            d['error_code'] = res.get('error_code')
            d['detail'] = str(res.get('detail'))[:160]
            d['completed_stage_ids'] = res.get('completed_stage_ids')
            d['execution_succeeded'] = (res.get('outcome') == 0)
        else:
            d['execution_succeeded'] = False
            d['outcome'] = None
            d['completed_stage_ids'] = None

        # --- independent evaluation (frozen evaluator on measured truth)
        gt = json.load(open(os.path.join(rd, 'ground_truth.json'), encoding='utf-8'))
        d['gt_source'] = gt.get('source')
        observed = order_from_stage_ids(d.get('completed_stage_ids'))
        state = {'objects': gt.get('objects') or {},
                 'move_sequence': observed,
                 'visits': {}}
        verdict = evaluator.evaluate(spec, state)
        d['evaluation_passed'] = verdict['passed']
        d['failed_clauses'] = verdict['failed_clauses']
        d['observed_sequence'] = observed
        d['evaluator_version'] = verdict['evaluator_version']
        rows.append(d)

    n = len(rows)
    pc = sum(1 for r in rows if r['planning_correct'])
    es = sum(1 for r in rows if r['execution_succeeded'])
    ep = sum(1 for r in rows if r['evaluation_passed'])

    # --- B's numbers, read from the archive (not re-run)
    brows = []
    for task_id in ids:
        rd = os.path.join(B_RUNS, task_id)
        rec = json.load(open(os.path.join(rd, 'recovery_decision.json'), encoding='utf-8'))
        act = rec.get('action')
        nested = (rec.get('decision') or {}).get('action')
        eff = act if act is not None else nested
        fe = json.load(open(os.path.join(rd, 'failure_evidence.json'), encoding='utf-8'))
        v1 = json.load(open(os.path.join(rd, 'observation_after1.json'), encoding='utf-8'))
        vf = json.load(open(os.path.join(rd, 'observation.json'), encoding='utf-8'))
        brows.append({'task_id': task_id,
                      'exec': fe.get('outcome') == 0 and eff in (None, 'no_recovery'),
                      'eval1': None, 'evalf': None,
                      'obs1': v1, 'obsf': vf})
    # B's eval requires its own spec; reuse the same reconstruction
    for b in brows:
        public = json.load(open(os.path.join(PUBLIC, b['task_id'] + '.json'),
                                encoding='utf-8'))
        goal = reconstruct_goal(public['instruction'], public)
        spec = dict(public)
        spec['expected_goal'] = goal
        spec['constraints'] = {'order': goal['order'], 'must_not_move': []}
        spec['template_id'] = 'T14_ordered_pair'
        def g(obs):
            return evaluator.evaluate(spec, {
                'objects': obs.get('objects') or {},
                'move_sequence': obs.get('move_sequence') or [],
                'visits': obs.get('visits') or {}})['passed']
        b['eval1'] = g(b['obs1'])
        b['evalf'] = g(b['obsf'])
    bpc = 16  # measured earlier: B's plan matched required order 16/16
    bes = sum(1 for b in brows if b['exec'])
    be1 = sum(1 for b in brows if b['eval1'])
    bef = sum(1 for b in brows if b['evalf'])

    print('=' * 82)
    print('A-PRIME vs B on the 16 T14 instances - SAME executor, SAME evaluator')
    print('=' * 82)
    print()
    print('  %-34s %-12s %-12s' % ('metric', 'A-prime', 'B (deepseek)'))
    print('  ' + '-' * 78)
    print('  %-34s %-12s %-12s' % ('planning_correct',
          '%d/%d' % (pc, n), '%d/%d' % (bpc, n)))
    print('  %-34s %-12s %-12s' % ('execution_succeeded (1st attempt)',
          '%d/%d' % (es, n), '%d/%d' % (bes, n)))
    print('  %-34s %-12s %-12s' % ('independent_evaluation_passed (1st)',
          '%d/%d' % (ep, n), '%d/%d' % (be1, n)))
    print('  %-34s %-12s %-12s' % ('evaluation_passed (after recovery)',
          'N/A (no recovery)', '%d/%d' % (bef, n)))
    print('  %-34s %-12s %-12s' % ('model calls (cost)', '0', str(n)))
    print()
    print('  %-18s %-9s %-9s %-9s %s' % ('run', 'plan', 'exec', 'eval', 'outcome/err'))
    print('  ' + '-' * 74)
    for r in rows:
        print('  %-18s %-9s %-9s %-9s %s/%s'
              % (r['task_id'], r['planning_correct'], r['execution_succeeded'],
                 r['evaluation_passed'], r.get('outcome'), r.get('error_code')))
    print()
    os.makedirs(os.path.join(HERE, 'grading'), exist_ok=True)
    with open(os.path.join(HERE, 'grading', 'aprime_vs_b.json'), 'w',
              encoding='utf-8') as f:
        json.dump({'n': n,
                   'aprime': {'planning': pc, 'execution': es, 'eval_first': ep,
                              'eval_after_recovery': None, 'model_calls': 0},
                   'b': {'planning': bpc, 'execution': bes, 'eval_first': be1,
                         'eval_after_recovery': bef, 'model_calls': n},
                   'rows': rows}, f, indent=2, default=str)
    print('  wrote grading/aprime_vs_b.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
