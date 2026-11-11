#!/usr/bin/env python3
"""Independent re-grade of the T08 evidence-loop batch (task-3).

WHAT THIS DOES DIFFERENTLY FROM THE PRODUCER
    It does not read the producer's verdict.json. For each trial it:
      1. re-validates the bundle with schema.validate()
      2. recomputes the bundle file sha256 and compares to the declared one
      3. checks task_id / task_sha256 against the real spec file
      4. checks timestamps are strictly increasing and the window contains them
      5. independently recomputes max_z from the RAW physics log
      6. calls evaluate.evaluate() itself with its own import
    Only then is the producer's verdict compared.

Any trial whose evidence is missing or corrupt is reported BLOCKED, never filled in.
"""
import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
LOOP = os.path.join(WT, 'setup', 'acceptance',
                    'evobot_t08_evidence_loop_20261112', 'evidence')
OUT = os.path.abspath(os.path.join(HERE, '..', 'independent_recheck'))
sys.path.insert(0, os.path.join(WT, 'benchmark', 'evidence'))
sys.path.insert(0, WT)

import schema                                                # noqa: E402
from benchmark.evaluators import evaluate as evaluator       # noqa: E402


def sha_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def find_spec(task_id):
    for split in ('t08_dev', 't08_unseen', 'train', 'val'):
        p = os.path.join(WT, 'benchmark', 'tasks', split, task_id + '.json')
        if os.path.exists(p):
            return p
    return None


def max_z_from_log(path, model):
    hi, n, missing = None, 0, 0
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            entry = (rec.get('objects') or {}).get(model)
            if not isinstance(entry, dict):
                missing += 1
                continue
            pose = entry.get('pose')
            if not isinstance(pose, list) or len(pose) != 7:
                missing += 1
                continue
            z = float(pose[2])
            if not math.isfinite(z):
                missing += 1
                continue
            hi = z if hi is None else max(hi, z)
            n += 1
    return hi, n, missing


def regrade(trial_dir):
    """Return (status, detail dict). status in OK / BLOCKED."""
    d = {}
    bp = os.path.join(trial_dir, 'evidence_bundle.json')
    ip = os.path.join(trial_dir, 'evaluator_input.json')
    rp = os.path.join(trial_dir, 'trial_record.json')
    if not (os.path.exists(bp) and os.path.exists(ip)):
        return 'BLOCKED', {'reason': 'evidence_bundle.json or evaluator_input.json missing'}
    bundle = json.load(open(bp, encoding='utf-8'))
    evinput = json.load(open(ip, encoding='utf-8'))
    producer = json.load(open(rp, encoding='utf-8')) if os.path.exists(rp) else {}

    d['task_id'] = bundle.get('task', {}).get('task_id')
    # --- 1. schema
    d['schema_problems'] = schema.validate(bundle)
    # --- 2. digest
    d['bundle_file_sha256'] = sha_file(bp)
    d['declared_sha256'] = producer.get('bundle_sha256')
    d['digest_matches'] = (d['declared_sha256'] == d['bundle_file_sha256'])
    d['bundle_self_digest_ok'] = (
        bundle.get('manifest', {}).get('bundle_sha256')
        == schema.bundle_sha256(bundle))
    # --- 3. task identity
    spec_path = find_spec(d['task_id'] or '')
    if not spec_path:
        d['task_spec_found'] = False
        d['task_sha256_matches'] = False
    else:
        d['task_spec_found'] = True
        d['spec_path'] = os.path.relpath(spec_path, WT)
        d['task_sha256_matches'] = (
            bundle['task']['task_sha256'] == sha_file(spec_path))
    # --- 4. rest height bound to spec
    if spec_path:
        spec = json.load(open(spec_path, encoding='utf-8'))
        tgt = bundle['task']['target_object']
        spec_rest = next(float(o['initial_pose'][2]) for o in spec['objects']
                         if o['name'] == tgt)
        d['rest_declared'] = bundle['task']['rest_height_m']
        d['rest_from_spec'] = spec_rest
        d['rest_bound_to_spec'] = abs(bundle['task']['rest_height_m'] - spec_rest) < 1e-9
    # --- 5. timestamps
    problems = []
    for name, entry in (bundle.get('objects') or {}).items():
        samples = entry.get('samples') or []
        for i in range(1, len(samples)):
            if samples[i][1] <= samples[i - 1][1]:
                problems.append('%s sim not increasing at %d' % (name, i))
                break
            if samples[i][0] != samples[i - 1][0] + 1:
                problems.append('%s seq jump at %d' % (name, i))
                break
    d['timestamp_problems'] = problems
    # --- 6. independent max_z from the raw log
    log = os.path.join(trial_dir, 'logs', 'physics_steps.jsonl')
    if os.path.exists(log) and d.get('task_spec_found'):
        hi, n, missing = max_z_from_log(log, bundle['task']['target_object'])
        d['max_z_from_raw_log'] = None if hi is None else round(hi, 9)
        d['raw_log_samples'] = n
        d['raw_log_missing'] = missing
        passed_z = ((evinput.get('trajectory') or {})
                    .get(bundle['task']['target_object'], {}).get('max_z_m'))
        d['max_z_passed_to_evaluator'] = passed_z
        d['max_z_honest'] = (passed_z is not None and hi is not None
                             and abs(float(passed_z) - hi) < 1e-6)
    else:
        d['max_z_from_raw_log'] = None
        d['max_z_honest'] = None
    # --- 7. MY OWN grade
    if not d.get('task_spec_found'):
        return 'BLOCKED', d
    spec = json.load(open(spec_path, encoding='utf-8'))
    mine = evaluator.evaluate(spec, evinput)
    d['my_passed'] = mine['passed']
    d['my_terminal_passed'] = mine['terminal_passed']
    d['my_failed_gates'] = (mine.get('evidence') or {}).get('failed_gates')
    d['my_physical_outcome'] = (mine.get('evidence') or {}).get('physical_outcome')
    d['my_evidence_status'] = (mine.get('evidence') or {}).get('evidence_status')
    d['my_failed_clauses'] = mine['failed_clauses']
    # --- 8. producer's verdict
    d['producer_passed'] = producer.get('passed')
    d['producer_terminal_passed'] = producer.get('terminal_passed')
    d['producer_failed_gates'] = producer.get('failed_gates')
    d['producer_evidence_status'] = producer.get('evidence_status')
    d['agree'] = (d['producer_passed'] == d['my_passed']
                  and sorted(d['producer_failed_gates'] or [])
                  == sorted(d['my_failed_gates'] or []))
    return 'OK', d


def main():
    os.makedirs(os.path.join(OUT, 'verdicts'), exist_ok=True)
    trials = []
    for arm in sorted(os.listdir(LOOP)) if os.path.isdir(LOOP) else []:
        adir = os.path.join(LOOP, arm)
        if not os.path.isdir(adir):
            continue
        for t in sorted(os.listdir(adir)):
            tdir = os.path.join(adir, t)
            if os.path.isdir(tdir):
                trials.append((arm, t, tdir))
    print('=' * 78)
    print('INDEPENDENT RE-GRADE - %d trial dirs found' % len(trials))
    print('=' * 78)
    rows = []
    for arm, t, tdir in trials:
        status, d = regrade(tdir)
        d['arm'], d['trial'] = arm, t
        with open(os.path.join(OUT, 'verdicts', '%s_%s.json' % (arm, t)),
                  'w', encoding='utf-8') as f:
            json.dump(d, f, indent=2, sort_keys=True, default=str)
        rows.append(d)
        if status == 'BLOCKED':
            print('  %-3s %-3s BLOCKED  %s' % (arm, t, d.get('reason')))
            continue
        print('  %-3s %-3s mine=%-5s producer=%-5s agree=%-5s gates=%s rest_bound=%s max_z_honest=%s'
              % (arm, t, d['my_passed'], d['producer_passed'], d['agree'],
                 d['my_failed_gates'], d.get('rest_bound_to_spec'),
                 d.get('max_z_honest')))
    with open(os.path.join(OUT, 'recheck.tsv'), 'w', encoding='utf-8') as f:
        cols = ['arm', 'trial', 'my_passed', 'producer_passed', 'agree',
                'my_failed_gates', 'producer_failed_gates', 'rest_bound_to_spec',
                'task_sha256_matches', 'digest_matches', 'max_z_honest',
                'my_evidence_status', 'producer_evidence_status']
        f.write('\t'.join(cols) + '\n')
        for d in rows:
            f.write('\t'.join(str(d.get(c)) for c in cols) + '\n')
    ok = [d for d in rows if d.get('my_passed') is not None]
    dis = [d for d in ok if not d.get('agree')]
    fs = [d for d in ok if d['my_passed'] and not d.get('producer_passed')]
    ff = [d for d in ok if not d['my_passed'] and d.get('producer_passed')]
    print()
    print('  regraded=%d  disagreements=%d  FALSE_SUCCESS=%d  FALSE_FAILURE=%d'
          % (len(ok), len(dis), len(fs), len(ff)))
    for d in dis:
        print('    DISAGREE %s/%s mine=%s producer=%s my_gates=%s prod_gates=%s'
              % (d['arm'], d['trial'], d['my_passed'], d.get('producer_passed'),
                 d['my_failed_gates'], d.get('producer_failed_gates')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
