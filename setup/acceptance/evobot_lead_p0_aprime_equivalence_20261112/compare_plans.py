#!/usr/bin/env python3
"""Do A-prime and B produce the same EXECUTABLE plan on the 16 frozen T14 instances?

WHY THE COMPARISON IS ON EXECUTOR KEYS AND NOT ON THE RULE OUTPUT
    An earlier audit pass compared the rule planner's raw output against B's archived plan and got
    0/16 identical. That was not a disagreement about the task: B applies spread_destinations after
    planning, placing the two blocks at distinct points inside the bin, and A-prime's raw rule
    output does not. Once both go through the same executor plan builder, the difference vanishes.
    So the honest question is what gets EXECUTED, and that is what this compares.

REFUSES on an empty or one-sided comparison, because 0/0 would otherwise read as agreement.
"""
import glob
import json
import os
import sys

KEYS = ('stages', 'position_tolerance_m', 'clearance_m', 'motion_profile_id',
        'initial_objects')


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
APRIME = os.path.join(REPO, 'setup', 'acceptance',
                     'evobot_p0_aprime_execution_20261112', 'runs')
BARCH = os.path.join(REPO, 'setup', 'acceptance', 'evobot_crosstype_20261111',
                     'runs_T14_ordered_pair')


def main():
    a_runs = sorted(glob.glob(os.path.join(APRIME, 'HO-*')))
    if not a_runs:
        raise SystemExit('REFUSED: no A-prime runs under %s' % APRIME)

    same = differ = missing = 0
    details = []
    for run in a_runs:
        task_id = os.path.basename(run)
        a_path = os.path.join(run, 'plan.json')
        b_path = os.path.join(BARCH, task_id, 'plan.json')
        if not (os.path.exists(a_path) and os.path.exists(b_path)):
            missing += 1
            continue
        a_plan = json.load(open(a_path))
        b_plan = json.load(open(b_path))
        a_keys = {k: a_plan.get(k) for k in KEYS}
        b_keys = {k: b_plan.get(k) for k in KEYS}
        if a_keys == b_keys:
            same += 1
        else:
            differ += 1
            diff_keys = [k for k in KEYS if a_keys[k] != b_keys[k]]
            details.append((task_id, diff_keys))

    total = same + differ
    print('A-prime vs B, executor-relevant plan keys')
    print('  identical : %d' % same)
    print('  different : %d' % differ)
    print('  missing   : %d' % missing)
    print()
    if total == 0:
        raise SystemExit('REFUSED: compared 0 pairs; this cannot be read as agreement')
    for task_id, keys in details[:10]:
        print('  %s differs on %s' % (task_id, keys))
    print()
    if differ == 0:
        print('PLANS_IDENTICAL %d/%d - a zero-cost rule parser reproduces the LLM plan' % (same, total))
        print('B measurable planning value on T14: ZERO')
    else:
        print('PLANS_DIFFER %d/%d identical' % (same, total))
    print()
    print('NOTE: plan equivalence is not task equivalence. Execution and evaluation are')
    print('separate measurements and are not made by this script.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
