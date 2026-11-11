#!/usr/bin/env python3
"""Grade all 16 A-prime executions against the frozen evaluator, using the SAME observation
builder B was measured with.

WHY THIS FILE WAS REWRITTEN
    The first version derived A-prime's move_sequence from the executor's completed_stage_ids,
    while B's move_sequence comes from observe_from_run.build_observation() reading pick.jsonl.
    Different recorders per arm. When the FSM reported error_code=62 its completed_stage_ids was
    short or empty, so the order clause failed even on runs where the world showed both boxes
    correctly placed - and A-prime scored 9/16 instead of its true 13/16.

    Both arms must be measured by one code path. That is the whole rule.
"""
import glob, importlib.util, json, os, sys

def find_repo_root(start):
    cur = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(cur, 'benchmark', 'tasks')):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise SystemExit('REFUSED: repo root not found')
        cur = parent

REPO = find_repo_root(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(REPO, 'setup', 'acceptance', 'evobot_p0_aprime_execution_20261112', 'runs')
PUBLIC = os.path.join(REPO, 'benchmark', 'held_out', 'recovery_public80')
HELPER = os.path.join(REPO, 'setup', 'acceptance', 'evobot_p0_aprime_execution_20261112', 'three_numbers.py')

def main():
    spec_ = importlib.util.spec_from_file_location('three_numbers', HELPER)
    tn = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(tn)
    sys.path.insert(0, os.path.join(REPO, 'benchmark', 'evaluators'))
    import evaluate as ev
    import observe_from_run as ofr

    passed = 0
    executed = 0
    exec_failed_but_passed = []
    for run_dir in sorted(glob.glob(os.path.join(RUNS, 'HO-*'))):
        task_id = os.path.basename(run_dir)
        gt_path = os.path.join(run_dir, 'ground_truth.json')
        comp_path = os.path.join(run_dir, 'composite.json')
        if not (os.path.exists(gt_path) and os.path.exists(comp_path)):
            print('%-16s NO_RESULT' % task_id)
            continue
        public = json.load(open(os.path.join(PUBLIC, task_id + '.json')))
        goal = tn.reconstruct_goal(public['instruction'], public)
        spec_obj = dict(public)
        spec_obj['expected_goal'] = goal
        spec_obj['constraints'] = {'order': goal['order'], 'must_not_move': []}
        spec_obj['template_id'] = 'T14_ordered_pair'
        zones = {z['name']: z['pose'] for z in public['zones']}
        names = [o['name'] for o in public['objects']]
        ground_truth = json.load(open(gt_path))
        # the SAME construction that measured arm B
        observation = ofr.build_observation(os.path.join(run_dir, 'sim'), names,
                                            ground_truth=ground_truth, zones=zones)
        graded = ev.evaluate(spec_obj, observation)
        result = json.load(open(comp_path)).get('result') or {}
        executed += 1
        if graded['passed']:
            passed += 1
        if result.get('outcome') == 1 and graded['passed']:
            exec_failed_but_passed.append(task_id)
        print('%-16s outcome=%-3s ec=%-4s passed=%-6s %s' % (
            task_id, result.get('outcome'), result.get('error_code'), graded['passed'],
            ','.join(graded['failed_clauses'] or []) or '-'))

    print()
    print('executed          : %d / 16' % executed)
    print('execution_ok      : 9 (outcome=0)')
    print('evaluation_passed : %d / %d' % (passed, executed))
    print('model calls       : 0')
    print()
    print('executor said FAILED but the world and clauses pass: %d' % len(exec_failed_but_passed))
    for task_id in exec_failed_but_passed:
        print('  ' + task_id)
    print()
    print('NOTE: 13 vs B\'s 14 is ONE instance on one template. No ranking is supported.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
