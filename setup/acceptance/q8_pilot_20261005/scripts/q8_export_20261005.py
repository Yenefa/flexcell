"""Export exact runtime evidence bytes; raw JSON bypasses formatting hooks."""
import hashlib
import json
from pathlib import Path
import re
import shutil

runtime = Path('/home/ros/agentic_workcell_ws/setup/acceptance/q8_pilot_20261005')
destination = Path('/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/code-clone/setup/acceptance/q8_pilot_20261005')
scripts = Path('/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/pm-work')
entries = []


def copy_raw(source, relative):
    target = destination / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    source_bytes = source.read_bytes()
    if target.exists() and target.read_bytes() != source_bytes:
        raise RuntimeError('refusing to replace changed evidence: %s' % target)
    target.write_bytes(source_bytes)
    digest = hashlib.sha256(source_bytes).hexdigest()
    assert hashlib.sha256(target.read_bytes()).hexdigest() == digest
    entries.append(dict(original=str(source), copy=str(relative),
                        sha256=digest, size=len(source_bytes)))


for source in sorted(runtime.iterdir()):
    if not source.is_file() or source.name == 'summary.json':
        continue
    suffix = '.raw' if source.suffix in ('.json', '.jsonl') else ''
    copy_raw(source, Path('runtime') / (source.name + suffix))
    if source.suffix == '.log':
        sessions = re.findall(r'GATE session: (.+)', source.read_text())
        for name in sessions:
            if not name.startswith('/mnt/f/flexcell-stage/'):
                continue  # pytest fixture sessions are already preserved in red/green logs
            session = Path(name)
            for artifact in sorted(session.iterdir()):
                if artifact.is_file():
                    copy_raw(artifact, Path('regression_sessions') / session.name / artifact.name)
        batches = re.findall(r'batch summary: (.+)', source.read_text())
        for name in batches:
            batch = Path(name)
            copy_raw(batch, Path('batches') / (batch.name + '.raw'))
            for line in batch.read_text().splitlines():
                row = json.loads(line)
                if row.get('episode'):
                    episode = Path(row['episode'])
                    copy_raw(episode, Path('episodes') / (episode.name + '.raw'))

for name in ('q8_progress_20261005.sh', 'q8_probe_20261005.py',
             'q8_report_20261005.py', 'q8_source_sync_20261005.py',
             'q8_export_20261005.py', 'q8_worker_probe_20261005.py',
             'q8_native_worker_probe_20261005.py', 'q8_native_diag_20261005.sh',
             'q8_abort_trace_20261005.c', 'q8_server_identity_20261005.ps1'):
    copy_raw(scripts / name, Path('scripts') / name)

if (runtime / 'summary.json').exists():
    shutil.copyfile(runtime / 'summary.json', destination / 'summary.json')

manifest = dict(format='immutable-byte-copies-v1',
    note='JSON/JSONL copies use .raw suffix to retain exact calibration/deployment/episode bytes through formatting hooks.',
    entries=entries)
(destination / 'SHA256SUMS.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(dict(files=len(entries), bytes=sum(e['size'] for e in entries),
                     destination=str(destination)), indent=2))
