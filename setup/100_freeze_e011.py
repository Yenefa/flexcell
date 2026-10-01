#!/usr/bin/env python3
"""Freeze E-011 v1 evidence, including originals and explicitly corrected reports."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--store', type=Path, required=True)
    args = ap.parse_args()
    root = Path(__file__).resolve().parent.parent
    dst = root / 'setup/acceptance/e011_protocol_v1_frozen_20260930'
    dst.mkdir(parents=True, exist_ok=True)
    manifest = {'experiment': 'E-011', 'protocol_id': 'flexcell-benchmark-v1',
                'status': 'ARCHIVED_NOT_COMPARABLE_WITH_V2',
                'source_commit': subprocess.check_output(
                    ['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                'erratum_date': '2026-09-30',
                'erratum': 'Metric 3 truncated integer-ms timing is NOT_RUN; raw episodes unchanged.',
                'files': [], 'missing': []}

    def save(rel, content, source):
        path = dst / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != content:
            raise RuntimeError('refusing to overwrite a frozen artifact: ' + str(path))
        path.write_bytes(content)
        manifest['files'].append({'path': rel, 'source': source,
                                  'sha256': hashlib.sha256(content).hexdigest()})

    for name in ['m3_baseline_t6_20260929', 'm3_seed_batch_20260929',
                 'm3_seed_batch_20260929_clean']:
        rel = 'setup/acceptance/%s/95_metrics_report.md' % name
        original = subprocess.check_output(['git', 'show', 'HEAD:' + rel], cwd=root)
        save('reports/%s_original.md' % name, original, 'HEAD:' + rel)
        save('reports/%s_corrected.md' % name, (root / rel).read_bytes(), rel)
    episode_paths = set()
    for path in sorted((root / 'setup/acceptance/m3_baseline_t6_20260929').glob('seg_*.jsonl')):
        save('batches/' + path.name, path.read_bytes(), str(path.relative_to(root)))
        for line in path.read_text().splitlines():
            episode_paths.add(json.loads(line)['episode'])
    for source in sorted(episode_paths):
        path = args.store / Path(source).name
        if path.exists():
            save('episodes/' + path.name, path.read_bytes(), source)
        else:
            manifest['missing'].append(source)
    manifest['episode_count'] = len(episode_paths) - len(manifest['missing'])
    if manifest['missing']:
        manifest['status'] = 'ARCHIVE_INCOMPLETE'
    (dst / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'archive': str(dst), 'episodes': manifest['episode_count'],
                      'missing': len(manifest['missing']), 'status': manifest['status']}))
    return 1 if manifest['missing'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
