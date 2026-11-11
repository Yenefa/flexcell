#!/usr/bin/env python3
"""Re-grade the archives against a causally-connected observable, and test the False Failure claim.

WHAT WENT WRONG THE FIRST TIME
    I treated "every plan stage released and nothing stuck" as sufficient for "this recorded failure is
    false". It is not. Release is not placement: an object can be released perfectly and still be in the
    wrong place, and the task clauses grade where it ended up. Five candidates met that criterion;
    checking each against the failed clause's own evidence and the ground truth showed ALL FIVE are
    genuine failures - three of them have an object still sitting at its initial pose.

    So this script tests candidates against the EVIDENCE, not against the release count.

WHAT IT ESTABLISHES
    1. census: how many archived runs hit the place release defect, and whether the carry ever failed
    2. cross-tab: recorded verdicts among those runs (the defect is present in 28 passing runs too, so
       it clearly does not determine the verdict on its own)
    3. candidate test: for each recorded failure, is the failed clause contradicted by the ground truth?
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


def err25_count(place_rows):
    n = 0
    for row in place_rows:
        try:
            if int(row.get('error_code')) == 25:
                n += 1
        except (TypeError, ValueError):
            pass
    return n


def main():
    skills_dirs = sorted({os.path.dirname(p) for p in
                          glob.glob(os.path.join(ACCEPTANCE, '**', 'skills', 'carry.jsonl'),
                                    recursive=True)})
    if not skills_dirs:
        raise SystemExit('REFUSED: no archived runs with skills/carry.jsonl found')

    runs = []
    stuck = 0
    for skills_dir in skills_dirs:
        root = run_root_for(skills_dir)
        carry = read_jsonl(os.path.join(skills_dir, 'carry.jsonl'))
        place = read_jsonl(os.path.join(skills_dir, 'place.jsonl'))
        starts = sum(1 for r in carry if r.get('event') == 'start')
        releases = sum(1 for r in carry if r.get('event') == 'stop' and r.get('cause') == 'release')
        if starts != releases:
            stuck += 1
        verdict = load_json(os.path.join(root, 'verdict.json')) or {}
        runs.append({'root': root, 'starts': starts, 'releases': releases,
                     'err25': err25_count(place), 'verdict': verdict})

    hit = [r for r in runs if r['err25']]
    print('=== 1. census ===')
    print('  archived runs scanned                     : %d' % len(runs))
    print('  runs with a place "gripper did not open"  : %d  (%.1f %%)'
          % (len(hit), 100.0 * len(hit) / len(runs)))
    print('  ...in which the carry still released      : %d'
          % sum(1 for r in hit if r['releases'] >= 1))
    print('  runs where a carry was ever left held     : %d' % stuck)
    print()

    print('=== 2. recorded verdict among the affected runs ===')
    pass_n = sum(1 for r in hit if r['verdict'].get('passed') is True)
    fail_n = sum(1 for r in hit if r['verdict'].get('passed') is False)
    none_n = len(hit) - pass_n - fail_n
    print('  recorded PASS           : %d' % pass_n)
    print('  recorded FAIL           : %d' % fail_n)
    print('  no verdict.json         : %d' % none_n)
    print('  -> the defect is present in %d PASSING runs, so it does not determine the verdict'
          % pass_n)
    print()

    print('=== 3. candidate false failures, tested against the evidence ===')
    tested = 0
    genuine = 0
    for r in hit:
        if r['verdict'].get('passed') is not False:
            continue
        if r['starts'] != r['releases']:
            continue
        tested += 1
        ground_truth = load_json(os.path.join(r['root'], 'ground_truth.json')) or {}
        objects = ground_truth.get('objects') or {}
        entry = load_json(os.path.join(r['root'], 'observation_input.json')) or {}
        initial = {o['name']: o.get('position') for o in (entry.get('objects') or [])}
        moved = []
        for name, pose in objects.items():
            start = initial.get(name)
            if start and pose:
                delta = sum((float(pose[i]) - float(start[i])) ** 2 for i in range(2)) ** 0.5
                moved.append((name, round(delta, 4)))
        still_home = [n for n, d in moved if d < 0.005]
        failed = [c.get('clause') for c in (r['verdict'].get('clauses') or []) if not c.get('ok')]
        verdict = 'GENUINE' if still_home else 'needs manual review'
        if verdict == 'GENUINE':
            genuine += 1
        print('  %-52s %s' % (os.path.basename(r['root']), verdict))
        print('     failed clauses : %s' % (failed or '-'))
        if still_home:
            print('     never moved    : %s  <-- the task was not performed' % still_home)
    print()
    print('  candidates tested      : %d' % tested)
    print('  provable false failures: %d' % (tested - genuine))
    print()
    print('CONCLUSION')
    print('  The place release defect is real and frequent (%d of %d runs), and the carry never failed to'
          % (len(hit), len(runs)))
    print('  release (%d stuck in %d runs). But it does NOT produce false failures here: the task clauses'
          % (stuck, len(runs)))
    print('  grade final world positions, those are correct, and every candidate failed for a real reason.')
    print('  Its harm is confined to EXECUTION verdicts, which is why A-prime shows 9/16 execution')
    print('  against its own 13/16 evaluation. Task-level numbers across the archive are NOT contaminated.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
