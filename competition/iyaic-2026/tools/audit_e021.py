#!/usr/bin/env python3
"""Recount E-021 summaries and inventory episode files; never run ROS/models.

Exit 0: inventory complete (not model replay or physical acceptance).
Exit 1: summaries recounted but episode files missing/ambiguous.
Exit 2: input/schema error. Output files are created exclusively.
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


BATCHES = (
    ('fsm', 'batch_20261005_185833.jsonl'),
    ('hybrid_0.03', 'batch_20261005_161922.jsonl'),
    ('hybrid_0.85', 'batch_20261005_192253.jsonl'),
)
SOURCE = Path('setup/acceptance/tau_sweep_desktop_20261005')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError('non-finite JSON constant: ' + value)


def rows(path):
    result = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        row = json.loads(line, object_pairs_hook=unique_object,
                         parse_constant=reject_constant)
        if not isinstance(row, dict):
            raise ValueError(str(path) + ': expected JSON objects')
        result.append(row)
    if not result:
        raise ValueError(str(path) + ': empty summary')
    return result


def recount(path, repo):
    records = rows(path)
    outcomes = Counter(row.get('outcome', 'UNKNOWN') for row in records)
    fingerprints = sorted({row['runtime_fingerprint'] for row in records
                           if row.get('runtime_fingerprint')})
    stages = sorted({row.get('stage', 'UNKNOWN') for row in records})
    references = [row.get('episode') for row in records]
    if any(not isinstance(value, str) or not value for value in references):
        raise ValueError(str(path) + ': missing episode reference')
    if len(set(references)) != len(references):
        raise ValueError(str(path) + ': duplicate episode references')
    dual = 0
    failure_signatures = Counter()
    for row in records:
        output = row.get('client_output', '')
        if 'RESULT ' not in output:
            continue
        # The nested legacy client text may contain NaN for unmeasured fields.
        # Only field presence is inspected, never treated as measured success.
        result, _ = json.JSONDecoder().raw_decode(output.split('RESULT ', 1)[1])
        dual += isinstance(result, dict) and all(
            key in result for key in ('object_a_at_zone', 'object_b_at_zone'))
        if row.get('outcome') == 'FAILED':
            if (isinstance(result, dict) and
                    result.get('error_code') == 'ERR_RECOVERY_EXHAUSTED' and
                    any('ERR_GRASP_FAILED' in step for step in result.get('fsm_trace', []))):
                failure_signatures['GRASP_FAILED_THEN_RECOVERY_EXHAUSTED'] += 1
            else:
                failure_signatures['UNCLASSIFIED_CLIENT_FAILURE'] += 1
    return {
        'summary': str(path.relative_to(repo)), 'sha256': digest(path),
        'attempted_rows': len(records), 'outcomes': dict(sorted(outcomes.items())),
        'completed_rows': len(records) - outcomes['HARNESS_ERROR'] - outcomes['UNKNOWN'],
        'successful_rows': outcomes['SUCCEEDED'],
        'harness_error_rows': sum(bool(row.get('harness_error')) for row in records),
        'stages': stages, 'runtime_fingerprints': fingerprints,
        'dual_object_client_results': dual,
        'client_failure_signatures': dict(sorted(failure_signatures.items())),
        'episode_basenames': [Path(value).name for value in references],
    }


def audit(repo):
    archive = repo / SOURCE
    index = defaultdict(list)
    for path in (repo / 'setup/acceptance').rglob('*.json'):
        if path.is_file():
            index[path.name].append(path)
    baselines = []
    for arm, name in BATCHES:
        item = recount(archive / name, repo)
        if item['stages'] != ['baseline'] or item['attempted_rows'] != 20:
            raise ValueError(name + ': unexpected E-021 stage/count')
        item['arm'] = arm
        inventory = []
        for basename in item.pop('episode_basenames'):
            candidates = index.get(basename, [])
            inventory.append({
                'basename': basename,
                'status': 'MISSING' if not candidates else
                          'FOUND_NOT_REPLAYED' if len(candidates) == 1 else 'AMBIGUOUS',
                'candidates': [{'path': str(path.relative_to(repo)),
                                'sha256': digest(path)} for path in candidates],
            })
        item['episode_inventory'] = inventory
        baselines.append(item)
    smoke = recount(archive / 'pooled_smoke_085.jsonl', repo)
    smoke.pop('episode_basenames')
    smoke['derived_pool_not_additional_trials'] = True
    states = Counter(entry['status'] for item in baselines
                     for entry in item['episode_inventory'])
    complete = states['MISSING'] == 0 and states['AMBIGUOUS'] == 0
    return {
        'record_kind': 'SUMMARY_INVENTORY_AUDIT',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'E-021 archived JSONL recount and basename inventory under setup/acceptance',
        'status': 'INVENTORY_COMPLETE_NOT_REPLAYED' if complete else 'EPISODE_ARCHIVE_INCOMPLETE',
        'baselines': baselines, 'pooled_smoke_0.85': smoke,
        'episode_inventory_counts': dict(sorted(states.items())),
        'model_replay': 'NOT_RUN', 'live_model_calls': 'NOT_RUN',
        'robot_execution': 'NOT_RUN', 'smoke_qualification': 'NOT_REASSESSED',
        'limitations': [
            'FOUND means a basename candidate exists, not validated episode identity or replay.',
            'No physical success, safety, calibrated accuracy or policy superiority is established.',
            'Baseline arms and pooled smoke are separate; no pooled success rate is computed.',
            'Original files and their failed outcomes are read-only.',
            'Failure signatures do not identify physical root causes or equal confounding across arms.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--out', type=Path, help='exclusive new JSON report; default stdout')
    args = parser.parse_args()
    try:
        report = audit(args.repo.resolve())
        rendered = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        if args.out:
            with args.out.open('x', encoding='utf-8') as output:
                output.write(rendered)
            print(report['status'] + ': ' + str(args.out))
        else:
            print(rendered, end='')
        return 0 if report['status'] == 'INVENTORY_COMPLETE_NOT_REPLAYED' else 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, 'audit error: %s\n' % error)


if __name__ == '__main__':
    raise SystemExit(main())
