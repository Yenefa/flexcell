#!/usr/bin/env python3
"""Archive a single API result with its correlated episode and deployment."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--log-dir', required=True)
    ap.add_argument('--deployment', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--store', default=str(Path.home() / '.ros/flexcell/episodes'))
    args = ap.parse_args()
    src, out = Path(args.log_dir), Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    text = (src / 'llm_single.out').read_text()
    result, _ = json.JSONDecoder().raw_decode(text.split('RESULT ', 1)[1])
    matches = []
    for path in Path(args.store).glob('*.json'):
        record = json.loads(path.read_text())
        if record.get('final_state', {}).get('evidence_id') == result['evidence_id']:
            matches.append((path, record))
    if len(matches) != 1:
        raise RuntimeError('single result did not match exactly one episode')
    path, record = matches[0]
    for filename in ('llm_single.out', 'llm_single_reset.json'):
        shutil.copyfile(src / filename, out / filename)
    shutil.copyfile(path, out / 'episode.json')
    shutil.copyfile(args.deployment, out / 'deployment.json')
    sources = {}
    for step in record['steps']:
        source = (step['policy_output'].get('policy_trace') or {}).get('source', record['policy']['name'])
        sources[source] = sources.get(source, 0) + 1
    manifest = dict(stage='SINGLE_API_SMOKE_OUTSIDE_BENCHMARK_CELLS',
                    outcome=result['outcome'], error_code=result['error_code'],
                    policy=record['policy'], runtime_fingerprint=record.get('runtime_fingerprint'),
                    actual_decision_sources=sources,
                    files_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted(out.iterdir()) if p.is_file()})
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
