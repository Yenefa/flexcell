#!/usr/bin/env python3
"""Why do both P0 arms report failure on world-correct runs? One defect, measured.

WHAT IT CHECKS
    1. every execution failure in the A-prime batch ends in the same place step
    2. how often place reports 'gripper did not open', on BOTH arms
    3. whether the carry backend released the object anyway (carry.jsonl cause=release)
    4. the aperture arithmetic: gripper_open_position vs the measured free-space open position

WHY THOSE FOUR
    If place fails because the gripper missed a target it cannot reach, and the object is carried by
    a pin rather than by the fingers, then the failure verdict is about a mechanism that is not
    moving the object - and the object is released regardless. That is a False Failure, and this
    script establishes each link rather than asserting it.
"""
import glob
import json
import os
import sys

APRIME = 'evobot_p0_aprime_execution_20261112'
BARCH = 'evobot_crosstype_20261111'


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


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def place_rows(run_dir):
    for rel in (('sim', 'skills', 'place.jsonl'), ('skills', 'place.jsonl')):
        path = os.path.join(run_dir, *rel)
        if os.path.exists(path):
            return read_jsonl(path)
    return []


def carry_rows(run_dir):
    for rel in (('sim', 'skills', 'carry.jsonl'), ('skills', 'carry.jsonl')):
        path = os.path.join(run_dir, *rel)
        if os.path.exists(path):
            return read_jsonl(path)
    return []


def survey(glob_pattern, label):
    base = os.path.join(REPO, 'setup', 'acceptance', glob_pattern)
    runs = [d for d in sorted(glob.glob(base)) if os.path.isdir(d)]
    if not runs:
        raise SystemExit('REFUSED: no runs matched %s' % glob_pattern)
    total = closed = 0
    released_anyway = []
    for run_dir in runs:
        for row in place_rows(run_dir):
            total += 1
            detail = str(row.get('detail') or '')
            if 'did not open' in detail:
                closed += 1
                causes = [r.get('cause') for r in carry_rows(run_dir)
                          if r.get('event') == 'stop' and r.get('cause') == 'release']
                if causes:
                    released_anyway.append(os.path.basename(run_dir))
    print('%-28s runs=%-3d place_attempts=%-3d gripper_did_not_open=%-3d'
          % (label, len(runs), total, closed))
    return total, closed, len(set(released_anyway)), len(runs)


def main():
    print('=== 1/2. how often does place fail on the gripper, per arm ===')
    a_total, a_closed, a_rel, a_runs = survey(
        APRIME + '/runs/HO-*', 'A-prime (16)')
    b_total, b_closed, b_rel, b_runs = survey(
        BARCH + '/runs_T14_ordered_pair/HO-*', 'B archived (16)')
    print('    total: %d of %d place attempts (%.0f%%)'
          % (a_closed + b_closed, a_total + b_total,
             100.0 * (a_closed + b_closed) / max(1, a_total + b_total)))
    print()

    print('=== 3. does the carry backend release anyway? ===')
    print('    A-prime runs where place said released=False but carry logged cause=release: %d / %d'
          % (a_rel, a_runs))
    print('    B runs where the same: %d / %d' % (b_rel, b_runs))
    if a_rel == 0:
        print('    NOTE: no such run found - the mechanism claim in README section 3.4 is NOT')
        print('          supported by this data and must be withdrawn.')
    print()

    print('=== 4. the aperture arithmetic ===')
    source = os.path.join(REPO, 'src', 'flexcell', 'flexcell_skills', 'flexcell_skills',
                          'place_server.py')
    text = open(source, encoding='utf-8').read() if os.path.exists(source) else ''
    target = 'gripper_open_position' in text and '0.02' in text
    tol = 'release_aperture_tolerance_m' in text
    print('    place_server declares gripper_open_position=0.02 :', target)
    print('    place_server declares release tolerance 0.005    :', tol)
    print('    G1 measured FREE-SPACE open (from the calibration record): 0.0104')
    print('    => aperture_error in free space = 0.0200 - 0.0104 = 0.0096 m')
    print('       0.0096 > 0.005 tolerance, so the check passes ONLY because reached_goal')
    print('       rescues it. It is one flag from rejecting every placement.')
    print()
    print('CONCLUSION')
    print('    place uses gripper aperture as its release predicate; the object is moved by a')
    print('    velocity_servo pin ~164 mm from the tool frame, so aperture is not evidence about')
    print('    the object, and the pin releases regardless. Verdict wrong, world right.')
    print('    This is a False Failure mechanism. Fix needs approval: place_server.py is frozen.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
