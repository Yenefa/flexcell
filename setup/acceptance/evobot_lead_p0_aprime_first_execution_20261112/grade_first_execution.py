#!/usr/bin/env python3
"""Grade A-prime's first execution. n=1, and every number here is a denominator of one."""
import importlib.util
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
TASK_ID = 'HO-0dcde4dc0f5a'
RUN = os.path.join(REPO, 'setup', 'acceptance', 'evobot_p0_aprime_execution_20261112',
                   'runs', TASK_ID)


def main():
    if not os.path.isdir(RUN):
        raise SystemExit('REFUSED: run directory missing: %s' % RUN)
    comp_path = os.path.join(RUN, 'composite.json')
    gt_path = os.path.join(RUN, 'ground_truth.json')
    for path in (comp_path, gt_path):
        if not os.path.exists(path):
            raise SystemExit('REFUSED: %s missing - nothing to grade' % path)

    # reuse the audited reconstruction rather than reading the root-only seal
    helper = os.path.join(REPO, 'setup', 'acceptance',
                          'evobot_p0_aprime_execution_20261112', 'three_numbers.py')
    module_spec = importlib.util.spec_from_file_location('three_numbers', helper)
    three_numbers = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(three_numbers)

    spec_obj, public = three_numbers.spec_for(TASK_ID)
    spec_obj['expected_goal'] = three_numbers.reconstruct_goal(
        spec_obj.get('instruction'), public)

    ground_truth = json.load(open(gt_path))
    composite = json.load(open(comp_path))
    result = composite.get('result') or {}
    stages = result.get('completed_stage_ids') or []
    move_sequence = [stage.rsplit('-', 1)[0] for stage in stages]

    sys.path.insert(0, os.path.join(REPO, 'benchmark', 'evaluators'))
    import evaluate as ev

    state = {'objects': ground_truth['objects'], 'move_sequence': move_sequence}
    graded = ev.evaluate(spec_obj, state)

    print('task            :', TASK_ID)
    print('evaluator       :', ev.EVALUATOR_VERSION)
    print('composite       : outcome=%s error_code=%s' % (result.get('outcome'),
                                                          result.get('error_code')))
    print('completed stages:', stages)
    print('move_sequence   :', move_sequence)
    print()
    for clause in graded['clauses']:
        print('  %-26s ok=%s' % (clause['clause'], clause['ok']))
    print()
    print('  passed          :', graded['passed'])
    print('  terminal_passed :', graded['terminal_passed'])
    print('  failed_clauses  :', graded['failed_clauses'])
    print()
    print('NOTE: n=1. This is one execution of sixteen planned. It establishes that the')
    print('pipeline works end to end at zero model cost. It establishes no pass RATE.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
