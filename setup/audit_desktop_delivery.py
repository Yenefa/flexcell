#!/usr/bin/env python3
"""Audit the frozen desktop ZIP without rewriting any experimental evidence.

Requires jsonschema. Exit 0 means complete evidence, 2 means a verified but
incomplete archive, and 1 means package/data consistency failure.
"""
import argparse
from collections import Counter, defaultdict
import copy
import hashlib
import json
from pathlib import Path
import zipfile

from jsonschema import Draft202012Validator

EXPECTED_ARCHIVE_SHA256 = '9aaee5fa2b24388c2523ebcb434a175bf4d2fbf72213987c0157df62b0eed30a'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def audit(path):
    if digest(path.read_bytes()) != EXPECTED_ARCHIVE_SHA256:
        raise ValueError('This auditor is scoped to the frozen 2026-10-23 delivery ZIP')
    with zipfile.ZipFile(path) as archive:
        files = {}
        for name in archive.namelist():
            normalized = name.replace('\\', '/')
            if normalized in files:
                raise ValueError('Duplicate archive name: ' + normalized)
            files[normalized] = archive.read(name)
    manifest = json.loads(files['MANIFEST.json'])
    for name, expected in manifest['files'].items():
        data = files[name]
        if len(data) != expected['bytes'] or digest(data) != expected['sha256']:
            raise ValueError('Manifest mismatch: ' + name)
    rows = [json.loads(line) for line in files['dataset/episodes.jsonl'].splitlines()]
    dataset = json.loads(files['dataset/dataset.json'])
    if dataset['episodes'] != rows:
        raise ValueError('dataset.json and episodes.jsonl disagree')
    raw = {}
    episode_refs = []
    for name, data in sorted(files.items()):
        if name.startswith('raw_batches/') and name.endswith('.jsonl'):
            for line in data.splitlines():
                row = json.loads(line)
                key = (Path(name).stem, row['scenario'], row['run'], row['seed'])
                if key in raw:
                    raise ValueError('Duplicate raw batch key: ' + repr(key))
                raw[key] = row
                episode_refs.append(row['episode'])
    if len(raw) != len(rows):
        raise ValueError('Raw and exported row counts differ')
    for row in rows:
        source = raw[(row['batch_id'], row['scenario'], row['run'], row['seed'])]
        for field in ['policy', 'stage', 'runtime_fingerprint', 'outcome', 'expected',
                      'model_decisions', 'harness_error', 'scenario_exercised']:
            if row[field] != source[field]:
                raise ValueError('Raw/export field mismatch: ' + field)
        if row['as_expected'] != (source['outcome'] == source['expected']):
            raise ValueError('as_expected disagrees with raw outcomes')
        marker = source['client_output'].find('RESULT ')
        result, _ = json.JSONDecoder().raw_decode(source['client_output'][marker + 7:])
        for field in ['detail', 'error_code', 'wall_seconds']:
            if row[field] != result[field]:
                raise ValueError('Client result/export mismatch: ' + field)
    schema = json.loads(files['dataset/schema.json'])
    errors = [e for row in rows for e in Draft202012Validator(schema).iter_errors(row)]
    corrected_schema = copy.deepcopy(schema)
    corrected_schema['properties']['batch_id']['type'] = ['string', 'null']
    corrected_errors = [e for row in rows
                        for e in Draft202012Validator(corrected_schema).iter_errors(row)]
    groups = defaultdict(list)
    for row in rows:
        groups[(row['runtime_fingerprint'], row['policy'], row['scenario'], row['stage'])].append(row)
    grouped = []
    for key, subset in sorted(groups.items()):
        grouped.append(dict(zip(['fingerprint', 'policy', 'scenario', 'stage'], key),
                            n=len(subset), succeeded=sum(r['outcome'] == 'SUCCEEDED' for r in subset),
                            as_expected=sum(r['as_expected'] for r in subset)))
    native = []
    for name, data in files.items():
        if name.endswith('.json'):
            obj = json.loads(data)
            if isinstance(obj, dict) and 'EpisodeSchemaVersion' in obj and 'steps' in obj:
                native.append(name)
    nonempty_ids = [r['run_id'] for r in rows if r['run_id']]
    missing_s4_codes = [r for r in rows if r['scenario'] == 'S4' and not r['detail_codes']]
    s7 = []
    for row in rows:
        if row['scenario'] == 'S7':
            inside = all(0.17 <= row[f'p_{o}_x'] <= 0.26
                         and -0.185 <= row[f'p_{o}_y'] <= 0.16 for o in ['a', 'b'])
            s7.append({k: row[k] for k in ['batch_id', 'run', 'seed', 'runtime_fingerprint',
                                          'outcome', 'as_expected', 'p_a_x', 'p_a_y', 'p_b_x', 'p_b_y']}
                      | {'inside_restricted_envelope': inside})
    report = {
        'scope': 'Frozen package integrity and batch-summary audit; no robot/model calls',
        'source_archive_sha256': digest(path.read_bytes()),
        'manifest_entries_verified': len(manifest['files']),
        'manifest_unlisted': sorted(set(files) - set(manifest['files'])),
        'raw_batches': sum(name.startswith('raw_batches/') for name in files),
        'rows': len(rows),
        'raw_export_consistency': 'PASS',
        'task_successes': sum(r['outcome'] == 'SUCCEEDED' for r in rows),
        'expected_failures': sum(r['outcome'] == r['expected'] == 'FAILED' for r in rows),
        'unexpected': sum(not r['as_expected'] for r in rows),
        'stage_counts': dict(Counter(r['stage'] for r in rows)),
        'fingerprint_counts': dict(Counter(r['runtime_fingerprint'] for r in rows)),
        'groups': grouped,
        'original_schema_errors': len(errors),
        'original_schema_error_paths': dict(Counter('.'.join(map(str, e.path)) for e in errors)),
        'corrected_schema_errors': len(corrected_errors),
        'missing_run_id_rows': sum(not r['run_id'] for r in rows),
        'duplicate_nonempty_run_ids': [k for k, n in Counter(nonempty_ids).items() if n > 1],
        'episode_references': len(episode_refs),
        'unique_episode_references': len(set(episode_refs)),
        'native_episode_files': len(native),
        'model_decisions_reported_by_runner': sum(r['model_decisions'] for r in rows),
        'model_trace_and_token_audit': 'UNAVAILABLE: native episode files absent',
        'model_replay': 'NOT_RUN',
        'fsm_replay': 'Batch PASS claims retained; not independently replayed here',
        'jev_s4_rows_missing_typed_cause': len([r for r in missing_s4_codes if r['policy'] == 'jev']),
        's7': s7,
        'status': 'INCOMPLETE_EVIDENCE',
        'findings': [
            'Original schema declares batch_id integer but all exported IDs are strings.',
            '30 S4 run_id fields are empty; raw batches retain distinct episode paths.',
            'Native episode files, per-decision model traces and measured tokens are not archived.',
            'Jev S4 typed skill causes are missing in the historical result detail.',
            'S7 includes old-envelope counterexamples; retain fingerprint, stage and actual placements.',
            'dataset/README.md is stale: it says fsm-only despite 55 jev rows.',
        ],
    }
    return report, corrected_schema


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--corrected-schema', type=Path)
    args = parser.parse_args()
    if args.out.exists() or (args.corrected_schema and args.corrected_schema.exists()):
        parser.error('Refusing to overwrite existing audit outputs')
    report, corrected = audit(args.archive)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    if args.corrected_schema:
        args.corrected_schema.parent.mkdir(parents=True, exist_ok=True)
        args.corrected_schema.write_text(json.dumps(corrected, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['rows', 'raw_export_consistency', 'original_schema_errors',
                                            'corrected_schema_errors', 'native_episode_files', 'status']}))
    return 2 if report['status'] == 'INCOMPLETE_EVIDENCE' else 0


if __name__ == '__main__':
    raise SystemExit(main())
