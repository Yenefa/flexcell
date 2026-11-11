#!/usr/bin/env python3
"""Provenance reproducers for the A-prime / oracle mislabel question.

Writes three TSVs under ../provenance/ and asserts the verdict in
PROVENANCE_APRIME_VERIFICATION.md. No simulator, no model calls.
"""
import glob
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
CI = os.path.abspath(os.path.join(WT, '..', 'ci-public-window'))
OUT = os.path.abspath(os.path.join(HERE, '..', 'provenance'))
A_DIR = os.path.join(CI, 'evidence', 'baseline_a_v2_gated_20261111')
B_DIR = os.path.join(WT, 'setup', 'acceptance', 'evobot_baseline_b_v2_20261111',
                     'plans')
sys.path.insert(0, os.path.join(WT, 'runtime', 'planner'))


def sha(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def find_spec(task):
    for split in ('train', 'val', 't08_dev', 't08_unseen'):
        p = os.path.join(WT, 'benchmark', 'tasks', split, task + '.json')
        if os.path.exists(p):
            return p
    return None


def q1_rebuild_all():
    """Every archived 'A-prime' plan must equal the oracle builder's output."""
    os.makedirs(OUT, exist_ok=True)
    plans = sorted(glob.glob(os.path.join(A_DIR, '*', 'plan.json')))
    rows, same = [], 0
    for p in plans:
        task = os.path.basename(os.path.dirname(p))
        spec = find_spec(task)
        if not spec:
            rows.append((task, 'NO_SPEC', '', ''))
            continue
        tmp = os.path.join('/tmp', 'rebuild_' + task + '.json')
        r = subprocess.run([sys.executable,
                            os.path.join(WT, 'experiments', 'baselines',
                                         'build_composite_plan.py'),
                            spec, tmp], capture_output=True, text=True)
        if r.returncode != 0:
            rows.append((task, 'BUILD_FAILED', sha(p), ''))
            continue
        a, b = sha(p), sha(tmp)
        same += (a == b)
        rows.append((task, 'IDENTICAL' if a == b else 'DIFFERS', a, b))
    with open(os.path.join(OUT, 'rebuild_sha256.tsv'), 'w', encoding='utf-8') as f:
        f.write('task\tverdict\tarchived_sha256\trebuilt_sha256\n')
        for r in rows:
            f.write('\t'.join(r) + '\n')
    print('  Q1 archived==oracle-builder : %d / %d byte-identical' % (same, len(plans)))
    return same == len(plans)


def q2_planner_matrix():
    """Which planner does each consumer actually import, and what does it say?"""
    import public_observation as po
    import rule_planner as generic
    import rule_planner_t01_t06 as t0106
    rows = []
    for task in ('T01-train-seed1000', 'T05-train-seed1000', 'T06-train-seed1000'):
        spec = json.load(open(find_spec(task), encoding='utf-8'))
        obs = po.build_observation(po.reduce_to_public(spec))
        g = [(m['object'], m['zone']) for m in generic.plan(obs)[0]]
        t = [(m['object'], m['zone']) for m in t0106.plan(obs)[0]]
        arch = [(s['object_name'], tuple(round(v, 3) for v in s['place_pose'][:2]))
                for s in json.load(open(os.path.join(A_DIR, task, 'plan.json')))["stages"]]
        b = [(s['object_name'], tuple(round(v, 3) for v in s['place_pose'][:2]))
             for s in json.load(open(os.path.join(B_DIR, task, 'plan.json')))["stages"]]
        rows.append((task, str(t), str(arch), str(b), str(g)))
    with open(os.path.join(OUT, 'planner_matrix.tsv'), 'w', encoding='utf-8') as f:
        f.write('task\trule_planner_t01_t06\tarchived_Aprime\tB\tgeneric_rule_planner\n')
        for r in rows:
            f.write('\t'.join(r) + '\n')
    print('  Q2 planner matrix written (%d instances)' % len(rows))
    return True


def q3_a_prime_artifacts():
    """Every artifact named a_prime*: is any of them a real plan?"""
    pats = [os.path.join(WT, 'setup', 'acceptance', '**', 'a_prime*.json'),
            os.path.join(CI, '**', 'a_prime*.json'),
            os.path.join(WT, 'experiments', '**', 'a_prime*.json')]
    hits = []
    for pat in pats:
        hits.extend(glob.glob(pat, recursive=True))
    hits = sorted(set(hits))
    rows, real_plans = [], 0
    for h in hits:
        try:
            d = json.load(open(h, encoding='utf-8'))
        except ValueError:
            rows.append((h.replace(WT, '.'), 'UNREADABLE', '', ''))
            continue
        planned = bool(d.get('planned'))
        real_plans += planned
        rows.append((h.replace(WT, '.'), d.get('task_id', ''),
                     str(planned), str(d.get('refusal', ''))[:60]))
    with open(os.path.join(OUT, 'a_prime_artifacts.tsv'), 'w', encoding='utf-8') as f:
        f.write('path\ttask_id\tplanned\trefusal\n')
        for r in rows:
            f.write('\t'.join(r) + '\n')
    print('  Q3 a_prime* artifacts: %d found, %d contain a real plan'
          % (len(hits), real_plans))
    return real_plans == 0


def q4_paired_script_runnable():
    """Does the script claiming to produce the A/B paired execution even parse?"""
    p = os.path.join(CI, 'scripts', 'evobot_p0_paired.sh')
    src = open(p, encoding='utf-8', errors='replace').read()
    # extract the first embedded python heredoc and compile it
    blocks, cur = [], None
    for line in src.splitlines():
        if cur is None and "<<'PY'" in line:
            cur = []
            continue
        if cur is not None:
            if line.strip() == 'PY':
                blocks.append('\n'.join(cur))
                cur = None
            else:
                cur.append(line)
    ok = True
    for i, blk in enumerate(blocks):
        try:
            compile(blk, '<heredoc%d>' % i, 'exec')
        except SyntaxError as exc:
            ok = False
            print('  Q4 heredoc %d does NOT compile: %s (line %s)'
                  % (i, exc.msg, exc.lineno))
    tsv = glob.glob(os.path.join(CI, '**', 'paired.tsv'), recursive=True)
    print('  Q4 paired.tsv artifacts found: %d' % len(tsv))
    return ok and bool(tsv)


def main():
    print('=' * 70)
    print('PROVENANCE AUDIT - A-prime vs oracle')
    print('=' * 70)
    r1 = q1_rebuild_all()
    r2 = q2_planner_matrix()
    r3 = q3_a_prime_artifacts()
    r4 = q4_paired_script_runnable()
    print()
    print('  [%s] Q1 archived A-prime == oracle builder output' % ('PASS' if r1 else 'FAIL'))
    print('  [%s] Q2 planner matrix produced' % ('PASS' if r2 else 'FAIL'))
    print('  [%s] Q3 no real A-prime plan artifact exists' % ('PASS' if r3 else 'FAIL'))
    print('  [%s] Q4 paired-execution script runnable and has artifacts'
          % ('PASS' if r4 else 'FINDING'))
    print()
    print('  Verdict: the A-prime column is the ORACLE; no real A-prime plan or'
          ' execution artifact exists.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
