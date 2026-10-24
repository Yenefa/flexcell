#!/usr/bin/env python3
"""Copy online evidence and hash it without modifying original episodes."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--batch', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--deployment', required=True)
    ap.add_argument('--runner-log', required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'episodes').mkdir()
    original = Path(args.batch)
    shutil.copyfile(original, out / 'batch_original.jsonl')
    shutil.copyfile(args.deployment, out / 'deployment.json')
    shutil.copyfile(args.runner_log, out / 'runner.log')
    rows = [json.loads(line) for line in original.read_text().splitlines() if line.strip()]
    plan = original.parent / 'batch_plans' / (original.stem + '.json')
    window = None
    if plan.is_file():
        # Keep an exact-byte copy with its original basename and plan. The
        # separate presentation JSONL below still rewrites absolute paths.
        window = out / 'qualification_window'
        (window / 'batch_plans').mkdir(parents=True)
        shutil.copyfile(original, window / original.name)
        shutil.copyfile(plan, window / 'batch_plans' / plan.name)
    for row in rows:
        if row.get('episode'):
            p = Path(row['episode'])
            if row.get('episode_relative') and (original.parent / row['episode_relative']).is_file():
                p = original.parent / row['episode_relative']
            elif not p.is_absolute():
                p = original.parent / p
            shutil.copyfile(p, out / 'episodes' / p.name)
            if window is not None:
                shutil.copyfile(p, window / p.name)
            row['episode'] = str(out / 'episodes' / p.name)
    with (out / 'batch_portable.jsonl').open('w') as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + '\n')
    facts = {}
    for row in rows:
        cell = row['scenario']
        f = facts.setdefault(cell, {'attempted': 0, 'harness_errors': 0,
                                  'task_succeeded': 0, 'expectation_matched': 0,
                                  'scenario_exercised': 0, 'episodes': 0,
                                  'actual_decision_sources': {}, 'final_error_codes': {}})
        f['attempted'] += 1
        f['harness_errors'] += row['outcome'] == 'HARNESS_ERROR'
        f['task_succeeded'] += row['outcome'] == 'SUCCEEDED'
        f['expectation_matched'] += row['outcome'] == row['expected']
        f['scenario_exercised'] += bool(row.get('scenario_exercised'))
        if not row.get('episode'):
            continue
        record = json.loads(Path(row['episode']).read_text())
        f['episodes'] += 1
        error = str(record['final_state']['error_code'])
        f['final_error_codes'][error] = f['final_error_codes'].get(error, 0) + 1
        for step in record['steps']:
            trace = (step.get('policy_output') or {}).get('policy_trace') or {}
            source = trace.get('source') or record['policy']['name']
            sources = f['actual_decision_sources']
            sources[source] = sources.get(source, 0) + 1
    files = {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(out.rglob('*')) if p.is_file()}
    manifest = dict(stage='ONLINE_SMOKE_NOT_STATISTICAL_BASELINE', source_batch=str(original),
                    cells=facts, files_sha256=files,
                    qualification_window=str(Path('qualification_window') / original.name)
                    if window is not None else None)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(facts, indent=2))


if __name__ == '__main__':
    main()
