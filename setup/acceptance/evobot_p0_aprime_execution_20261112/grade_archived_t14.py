#!/usr/bin/env python3
"""Grade the 16 archived T14 runs with the FROZEN evaluator - gradeability audit first.

THREE THINGS THE LEAD ASKED ME NOT TO ASSUME
  1. that the 16 runs are gradeable
  2. that they are A-prime runs (they are not - see the arm audit)
  3. that a full evidence bundle exists (it does not; these are T14 pick-place,
     not T08 push, so the 9-gate evidence layer does not apply to them)

GRADEABILITY CHAIN, verified rather than assumed:
  observation    observation.json carries measured objects + move_sequence
  ground truth   ground_truth.json, source GZ_GROUND_TRUTH
  spec           public spec in benchmark/held_out/recovery_public80/ (no answer)
  answer         sealed at /etc/evobot/sealed, root-only -> NOT READABLE HERE
                 so it is RECONSTRUCTED from the instruction, and the
                 reconstruction is validated against the archived verdicts
  evaluator      benchmark/evaluators/evaluate.py v0.5.0 (frozen)
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, WT)
from benchmark.evaluators import evaluate as evaluator   # noqa: E402

RUNS = os.path.join(WT, 'setup', 'acceptance', 'evobot_crosstype_20261111',
                    'runs_T14_ordered_pair')
PUBLIC = os.path.join(WT, 'benchmark', 'held_out', 'recovery_public80')


def reconstruct_goal(instruction, public):
    """Derive expected_goal from the instruction alone - the T14 template.

    T14 instruction shape:
      'Put both blocks in the <side> bin. The <colour> block must be put there
       FIRST, then the <colour> block. ...'

    Returns None if the instruction does not match, so a non-T14 instance is
    reported as ungradeable rather than silently mis-graded.
    """
    m = re.search(r'put both blocks in the (\w+) bin', instruction, re.I)
    if not m:
        return None
    side = m.group(1).lower()
    # resolve the side to a zone using MEASURED geometry, exactly as the
    # robot must: +y is the robot LEFT.
    zones = {z['name']: z['pose'] for z in public['zones']}
    by_side = sorted(zones, key=lambda n: zones[n][1], reverse=True)
    left, right = by_side[0], by_side[1]
    zone = left if side.startswith('l') else right

    m_first = re.search(r'the (\w+) block must be put there first', instruction, re.I)
    if not m_first:
        return None
    colour_to_name = {str(o.get('color', '')).lower(): o['name']
                      for o in public['objects']}
    first = colour_to_name.get(m_first.group(1).lower())
    m_then = re.search(r'then the (\w+) block', instruction, re.I)
    second = colour_to_name.get(m_then.group(1).lower()) if m_then else None
    if not (first and second):
        return None
    return {'placement': {first: zone, second: zone},
            'order': [first, second],
            'unmoved': []}


def grade_one(task_id):
    d = {'task_id': task_id, 'gradeable': False, 'reasons': []}
    rd = os.path.join(RUNS, task_id)
    pub_path = os.path.join(PUBLIC, task_id + '.json')
    for need, path in (('public spec', pub_path),
                       ('observation', os.path.join(rd, 'observation.json')),
                       ('ground truth', os.path.join(rd, 'ground_truth.json')),
                       ('archived plan', os.path.join(rd, 'plan.json'))):
        if not os.path.exists(path):
            d['reasons'].append('%s missing' % need)
    if d['reasons']:
        return d

    public = json.load(open(pub_path, encoding='utf-8'))
    obs = json.load(open(os.path.join(rd, 'observation.json'), encoding='utf-8'))
    gt = json.load(open(os.path.join(rd, 'ground_truth.json'), encoding='utf-8'))

    # ground truth must be real measured truth, not a claim
    d['gt_source'] = gt.get('source')
    if gt.get('source') != 'GZ_GROUND_TRUTH':
        d['reasons'].append('ground truth source is %r not GZ_GROUND_TRUTH'
                            % gt.get('source'))
    if gt.get('errors'):
        d['reasons'].append('ground truth reports errors: %r' % gt['errors'])

    goal = reconstruct_goal(public['instruction'], public)
    if goal is None:
        d['reasons'].append('instruction does not match the T14 template; the sealed '
                            'answer cannot be reconstructed' )
        return d
    d['reconstructed_goal'] = goal

    spec = dict(public)
    spec['expected_goal'] = goal
    spec['constraints'] = {'order': goal['order'], 'must_not_move': []}
    spec['template_id'] = 'T14_ordered_pair'

    state = {'objects': gt['objects'],
             'move_sequence': obs.get('move_sequence') or [],
             'visits': obs.get('visits') or {}}
    verdict = evaluator.evaluate(spec, state)
    d['gradeable'] = True
    d['passed'] = verdict['passed']
    d['failed_clauses'] = verdict['failed_clauses']
    d['evaluator_version'] = verdict['evaluator_version']
    d['clauses'] = verdict['clauses']

    # cross-check against the archived verdict's own order clause
    arch = json.load(open(os.path.join(rd, 'verdict.json'), encoding='utf-8'))
    arch_req = next((c['evidence']['required'] for c in arch['clauses']
                     if c['clause'] == 'order'), None)
    d['archived_required_order'] = arch_req
    d['reconstruction_matches_archive'] = (arch_req == goal['order'])
    d['archived_passed'] = arch.get('passed')
    d['archived_evaluator_version'] = arch.get('evaluator_version')
    return d


def main():
    ids = sorted(os.listdir(RUNS))
    outdir = os.path.join(HERE, 'grading')
    os.makedirs(outdir, exist_ok=True)
    print('=' * 80)
    print('GRADEABILITY AUDIT + FROZEN RE-GRADE of the 16 archived T14 runs')
    print('=' * 80)
    print('  runs found: %d' % len(ids))
    print()
    rows = [grade_one(i) for i in ids]

    gradeable = [r for r in rows if r['gradeable']]
    blocked = [r for r in rows if not r['gradeable']]
    print('  GRADEABLE   : %d' % len(gradeable))
    print('  NOT GRADEABLE: %d' % len(blocked))
    for b in blocked:
        print('    %s -> %s' % (b['task_id'], '; '.join(b['reasons'])))
    print()
    if gradeable:
        recon = sum(1 for r in gradeable if r['reconstruction_matches_archive'])
        print('  reconstruction agrees with archived order: %d/%d'
              % (recon, len(gradeable)))
        print()
        print('  %-18s %-8s %-8s %s' % ('run', 'frozen', 'archived', 'failed clauses (frozen)'))
        print('  ' + '-' * 74)
        for r in gradeable:
            print('  %-18s %-8s %-8s %s'
                  % (r['task_id'], r['passed'], r.get('archived_passed'),
                     r['failed_clauses'] or '-'))
        npass = sum(1 for r in gradeable if r['passed'])
        print('  ' + '-' * 74)
        print('  FROZEN EVALUATOR PASS: %d/%d' % (npass, len(gradeable)))

    with open(os.path.join(outdir, 'gradeability.json'), 'w',
              encoding='utf-8') as f:
        json.dump(rows, f, indent=2, default=str)
    print()
    print('  wrote grading/gradeability.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
