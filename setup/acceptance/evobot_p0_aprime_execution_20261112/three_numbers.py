#!/usr/bin/env python3
"""Three separate numbers for the 16 archived T14 runs.

WHY THREE NUMBERS AND NOT ONE
    planning_correct              did the PLAN name the right objects, in the right
                                  order, into the right zone
    execution_succeeded           did the robot's own FSM report all stages OK on
                                  the FIRST attempt, with no recovery
    independent_evaluation_passed did the frozen evaluator pass the measured end
                                  state (this is the only one that is evidence)

A run can be planning_correct and execution_succeeded and still fail evaluation,
or vice versa. Conflating them is the error this project keeps repeating.

THE RECOVERY SPLIT (the thing that makes the archive readable)
    observation.json           FINAL state, after recovery if any
    observation_after1.json    state after the FIRST attempt, before recovery
    14 runs needed no recovery, so the two are identical.
    2 runs failed the first attempt and were resumed; for those, grading the
    final state would silently credit recovery to the first attempt.

THIS IS NOT AN A-PRIME BATCH
    agent_reply.json carries requested_model/base_url/key_fingerprint: these
    runs are arm B (deepseek-flash). A-prime produced no plan in this archive.
    A-prime's plans are DERIVED here from the same observation for comparison,
    and that derivation is a PLAN, not an execution.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, WT)
sys.path.insert(0, os.path.join(WT, 'runtime', 'planner'))
from benchmark.evaluators import evaluate as evaluator   # noqa: E402
import rule_planner as rp                                # noqa: E402

RUNS = os.path.join(WT, 'setup', 'acceptance', 'evobot_crosstype_20261111',
                    'runs_T14_ordered_pair')
PUBLIC = os.path.join(WT, 'benchmark', 'held_out', 'recovery_public80')


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


def spec_for(task_id):
    public = json.load(open(os.path.join(PUBLIC, task_id + '.json'), encoding='utf-8'))
    goal = reconstruct_goal(public['instruction'], public)
    if goal is None:
        return None, None
    spec = dict(public)
    spec['expected_goal'] = goal
    spec['constraints'] = {'order': goal['order'], 'must_not_move': []}
    spec['template_id'] = 'T14_ordered_pair'
    return spec, public


def main():
    ids = sorted(os.listdir(RUNS))
    outdir = os.path.join(HERE, 'grading')
    os.makedirs(outdir, exist_ok=True)
    rows = []
    for task_id in ids:
        rd = os.path.join(RUNS, task_id)
        spec, public = spec_for(task_id)
        # The recovery record has TWO shapes: a flat {'action': 'no_recovery'} when
        # the first attempt was clean, and a nested {'decision': {'action': 'resume'}}
        # when it was not. Reading only the top-level key reports the 2 resumed runs
        # as "not recovered", which would credit their recovery to the first attempt.
        rec = json.load(open(os.path.join(rd, 'recovery_decision.json'), encoding='utf-8'))
        action = rec.get('action')
        nested = (rec.get('decision') or {}).get('action')
        effective = action if action is not None else nested
        recovered = effective not in (None, 'no_recovery')

        # --- 1. planning_correct: does the PLAN satisfy placement + order?
        plan = json.load(open(os.path.join(rd, 'plan.json'), encoding='utf-8'))
        stages = plan.get('stages') or []
        plan_seq = [s['object_name'] for s in stages]
        zones = {z['name']: z['pose'] for z in public['zones']}
        plan_ok = True
        for obj, zone_name in spec['expected_goal']['placement'].items():
            want = zones[zone_name]
            hit = [s for s in stages if s['object_name'] == obj]
            if not hit or (abs(hit[0]['place_pose'][0] - want[0]) > 0.06
                           or abs(hit[0]['place_pose'][1] - want[1]) > 0.06):
                plan_ok = False
        if plan_seq != spec['expected_goal']['order']:
            plan_ok = False

        # --- A-prime's own plan, for the head-to-head
        ap_moves, _, ap_note = rp.plan({
            'instruction': public['instruction'],
            'objects': [{'name': o['name'], 'color': o.get('color'),
                         'position': list(o['initial_pose'][:3])}
                        for o in public['objects']],
            'zones': [{'name': z['name'], 'position': list(z['pose']),
                       'radius': z['radius']} for z in public['zones']],
        })
        ap_seq = [m['object'] for m in ap_moves]
        ap_plan_ok = bool(ap_moves) and ap_seq == spec['expected_goal']['order']
        for m in ap_moves:
            want = zones[m['zone']]
            if abs(want[0] - zones[spec['expected_goal']['placement'][m['object']]][0]) > 1e-9:
                ap_plan_ok = False

        # --- 2. execution_succeeded: first attempt, no recovery, FSM all OK
        fe = json.load(open(os.path.join(rd, 'failure_evidence.json'), encoding='utf-8'))
        exec_ok = (fe.get('outcome') == 0 and not recovered)

        # --- 3. independent_evaluation_passed: frozen evaluator on measured state
        first = json.load(open(os.path.join(rd, 'observation_after1.json'), encoding='utf-8'))
        final = json.load(open(os.path.join(rd, 'observation.json'), encoding='utf-8'))
        def grade(obs):
            st = {'objects': obs.get('objects') or {},
                  'move_sequence': obs.get('move_sequence') or [],
                  'visits': obs.get('visits') or {}}
            return evaluator.evaluate(spec, st)
        v_first = grade(first)
        v_final = grade(final)

        rows.append({
            'task_id': task_id,
            'recovered': recovered,
            'recovery_action': effective,
            'planning_correct': plan_ok,
            'plan_sequence': plan_seq,
            'required_order': spec['expected_goal']['order'],
            'execution_succeeded_first_attempt': exec_ok,
            'evaluation_passed_first_attempt': v_first['passed'],
            'evaluation_passed_after_recovery': v_final['passed'],
            'failed_clauses_first': v_first['failed_clauses'],
            'aprime_planned': bool(ap_moves),
            'aprime_note': ap_note,
            'aprime_planning_correct': ap_plan_ok,
            'aprime_sequence': ap_seq,
            'aprime_same_plan_as_B': ap_seq == plan_seq,
        })

    n = len(rows)
    print('=' * 80)
    print('16 ARCHIVED T14 RUNS - three numbers, kept separate')
    print('=' * 80)
    print('  %-18s %-9s %-9s %-11s %-11s %s'
          % ('run', 'planning', 'exec(1st)', 'eval(1st)', 'eval(after)', 'recovered'))
    print('  ' + '-' * 76)
    for r in rows:
        print('  %-18s %-9s %-9s %-11s %-11s %s'
              % (r['task_id'], r['planning_correct'],
                 r['execution_succeeded_first_attempt'],
                 r['evaluation_passed_first_attempt'],
                 r['evaluation_passed_after_recovery'], r['recovered']))
    print('  ' + '-' * 76)
    pc = sum(1 for r in rows if r['planning_correct'])
    es = sum(1 for r in rows if r['execution_succeeded_first_attempt'])
    e1 = sum(1 for r in rows if r['evaluation_passed_first_attempt'])
    ea = sum(1 for r in rows if r['evaluation_passed_after_recovery'])
    print('  %-18s %-9s %-9s %-11s %-11s' % ('TOTAL /%d' % n,
          '%d/%d' % (pc, n), '%d/%d' % (es, n), '%d/%d' % (e1, n), '%d/%d' % (ea, n)))
    print()
    print('=' * 80)
    print('ARM COMPARISON (arm B = the archived LLM plans; A-prime = derived here)')
    print('=' * 80)
    apc = sum(1 for r in rows if r['aprime_planning_correct'])
    same = sum(1 for r in rows if r['aprime_same_plan_as_B'])
    print('  arm B planning_correct   : %d/%d' % (pc, n))
    print('  A-prime planning_correct : %d/%d' % (apc, n))
    print('  A-prime order == B order : %d/%d' % (same, n))
    print('  A-prime model calls      : 0')
    print()
    with open(os.path.join(outdir, 'three_numbers.json'), 'w', encoding='utf-8') as f:
        json.dump({'n': n, 'planning_correct': pc, 'execution_first': es,
                   'eval_first': e1, 'eval_after': ea,
                   'aprime_planning_correct': apc, 'aprime_same_as_B': same,
                   'rows': rows}, f, indent=2, default=str)
    print('  wrote grading/three_numbers.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
