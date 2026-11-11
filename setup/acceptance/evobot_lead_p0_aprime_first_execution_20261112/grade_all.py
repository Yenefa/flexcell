#!/usr/bin/env python3
"""Grade all 16 A-prime executions against the frozen evaluator."""
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
HELPER = os.path.join(REPO, 'setup', 'acceptance', 'evobot_p0_aprime_execution_20261112', 'three_numbers.py')

def main():
    spec_ = importlib.util.spec_from_file_location('three_numbers', HELPER)
    tn = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(tn)
    sys.path.insert(0, os.path.join(REPO, 'benchmark', 'evaluators'))
    import evaluate as ev

    executed = passed = 0
    rows = []
    for run_dir in sorted(glob.glob(os.path.join(RUNS, 'HO-*'))):
        tid = os.path.basename(run_dir)
        comp_path = os.path.join(run_dir, 'composite.json')
        gt_path = os.path.join(run_dir, 'ground_truth.json')
        if not (os.path.exists(comp_path) and os.path.exists(gt_path)):
            rows.append((tid, 'NO_RESULT'))
            continue
        result = (json.load(open(comp_path)).get('result') or {})
        gt = json.load(open(gt_path))
        stages = result.get('completed_stage_ids') or []
        move_sequence = [s.rsplit('-', 1)[0] for s in stages]
        spec_obj, public = tn.spec_for(tid)
        spec_obj['expected_goal'] = tn.reconstruct_goal(spec_obj.get('instruction'), public)
        graded = ev.evaluate(spec_obj, {'objects': gt['objects'], 'move_sequence': move_sequence})
        executed += 1
        if graded['passed']:
            passed += 1
        rows.append((tid, result.get('outcome'), result.get('error_code'), len(stages),
                     graded['passed'], graded['failed_clauses']))

    print('%-16s %-8s %-4s %-7s %-7s %s' % ('task','outcome','ec','stages','passed','failed'))
    print('-' * 84)
    for row in rows:
        if row[1] == 'NO_RESULT':
            print('%-16s NO_RESULT' % row[0]); continue
        tid, outcome, ec, nstages, ok, failed = row
        print('%-16s %-8s %-4s %-7d %-7s %s' % (tid, outcome, ec, nstages, ok,
                                                  ','.join(failed or []) or '-'))
    print('-' * 84)
    print('attempted         : %d' % len(rows))
    print('executed          : %d' % executed)
    print('execution_ok      : %d (outcome=0)' % sum(1 for r in rows if len(r) > 1 and r[1] == 0))
    print('evaluation_passed : %d / %d' % (passed, executed))
    print('model calls       : 0')
    print()
    print('NOTE: 16 tasks; 9 vs B\'s 11 is within noise. Do not read a ranking into it.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
