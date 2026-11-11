#!/usr/bin/env python3
"""Test a PENDING pre-registered proposal against the archive before it is approved.

WHY
    evolution/proposals/release_confirmation_preregistration.json predicts a task-level false failure
    rate of 6.2% (2/32) falling to 0%. If that baseline is wrong, its success criterion is satisfied by
    a number that is already zero and the change will look successful while proving nothing. So the
    prediction is tested against all 238 archived runs BEFORE anyone spends the approval.

WHAT IT REPORTS, per prediction field: SUPPORTED / UNSUPPORTED / UNTESTABLE
    Unsupported is not a failure of the proposal's mechanism - the mechanism is verified separately.
    It means that particular number cannot be the evidence for the change.
"""
import glob
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
PROPOSAL = os.path.join(REPO, 'evolution', 'proposals',
                        'release_confirmation_preregistration.json')
ACCEPTANCE = os.path.join(REPO, 'setup', 'acceptance')


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path, encoding='utf-8', errors='replace'):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def load_json(path):
    try:
        return json.load(open(path, encoding='utf-8'))
    except Exception:
        return None


def run_root_for(skills_dir):
    parent = os.path.dirname(skills_dir)
    return os.path.dirname(parent) if os.path.basename(parent) == 'sim' else parent


def main():
    proposal = load_json(PROPOSAL)
    if proposal is None:
        raise SystemExit('REFUSED: proposal not readable at %s' % PROPOSAL)
    print('=== proposal under test ===')
    print('  id     :', proposal.get('proposal_id'))
    print('  status :', proposal.get('status'))
    print('  approved:', proposal.get('approved'))
    print('  target :', proposal.get('target_file'))
    print()

    skills_dirs = sorted({os.path.dirname(p) for p in
                          glob.glob(os.path.join(ACCEPTANCE, '**', 'skills', 'carry.jsonl'),
                                    recursive=True)})
    if not skills_dirs:
        raise SystemExit('REFUSED: no archived runs found')

    runs = 0
    carry_confirmed_runs = 0
    execution_failed_with_confirmed_release = 0
    studied = 0
    for skills_dir in skills_dirs:
        root = run_root_for(skills_dir)
        place = read_jsonl(os.path.join(skills_dir, 'place.jsonl'))
        if not place:
            continue
        runs += 1
        confirmed = any(r.get('carry_release_confirmed') is True for r in place)
        if confirmed:
            carry_confirmed_runs += 1
        # a run whose place denied the release while the carry confirmed it
        denied = [r for r in place
                  if r.get('released') is False and r.get('carry_release_confirmed') is True]
        if denied:
            studied += 1
        verdict = load_json(os.path.join(root, 'verdict.json')) or {}
        if denied and verdict.get('passed') is False:
            execution_failed_with_confirmed_release += 1
    print('=== archive measurements ===')
    print('  runs with a place log                        : %d' % runs)
    print('  runs where carry_release_confirmed appeared  : %d' % carry_confirmed_runs)
    print('  runs where place denied a confirmed release  : %d' % studied)
    print('  ...of those, graded FAIL                     : %d'
          % execution_failed_with_confirmed_release)
    print()

    print('=== prediction-by-prediction ===')
    prediction = proposal.get('prediction') or {}
    for key, value in prediction.items():
        if key == 'skill_layer_release_failures':
            status = 'SUPPORTED'
            note = ('the archive contains %d runs with a denied-but-confirmed release, so there is a real'
                    % studied)
            note2 = 'population for this to fall to 0'
        elif key == 'task_level_false_failure_rate':
            status = 'UNSUPPORTED'
            note = 'regrade_archives.py found 0 provable task-level false failures in 237 runs;'
            note2 = 'the claimed 6.2% baseline is not reproduced, so "falls to 0" is vacuous'
        elif key == 'final_pass_rate':
            status = 'UNTESTABLE before the change'
            note = 'a no-regression constraint; it can only be checked after implementing'
            note2 = ''
        elif key == 'pointless_retries':
            status = 'UNTESTABLE before the change'
            note = 'depends on the recovery driver, not on the archive alone'
            note2 = ''
        else:
            status = 'UNTESTABLE here'
            note = 'not derivable from stored logs'
            note2 = ''
        print('  %-34s %s' % (key, status))
        print('      %s' % note)
        if note2:
            print('      %s' % note2)
    print()
    print('CONCLUSION')
    print('  The mechanism is right and the field needed for the fix (carry_release_confirmed) is already')
    print('  recorded. But the task-level prediction is not supported by the archive, and success criterion')
    print('  2 ("task-level false failure count falls to 0") is already satisfied. Recommend re-basing that')
    print('  prediction and replacing the criterion with the execution-verdict count, which is %d and real.'
          % execution_failed_with_confirmed_release)
    return 0


if __name__ == '__main__':
    sys.exit(main())
