"""Exercise the production subscriber without native instrumentation."""
import argparse
import json
from pathlib import Path
import sys
import time
from flexcell_skills.common import _ensure_gz_pose_stream, _GZ_STREAM, stop_gz_pose_stream

ap = argparse.ArgumentParser()
ap.add_argument('output')
ap.add_argument('--count', type=int, default=100)
ap.add_argument('--hold', type=float, default=.5)
args = ap.parse_args()
rows = []
for run in range(1, args.count + 1):
    _ensure_gz_pose_stream()
    time.sleep(args.hold)
    with _GZ_STREAM['lock']:
        worker = _GZ_STREAM.get('worker')
        row = dict(run=run, worker_pid=worker.pid if worker else None,
                   received_pose=_GZ_STREAM['last_rx'] > 0)
    try:
        stop_gz_pose_stream()
        row['ok'] = row['received_pose']
    except Exception as exc:
        row.update(ok=False, error=str(exc))
    with _GZ_STREAM['lock']:
        row.update(worker_rc=_GZ_STREAM.get('worker_rc'),
                   native_stderr_tail=_GZ_STREAM['cb_error'])
    rows.append(row)
    print(json.dumps(row), flush=True)
    Path(args.output).write_text(json.dumps(rows, indent=2) + '\n')
    if not row['ok']:
        break
sys.exit(0 if len(rows) == args.count and all(r['ok'] for r in rows) else 1)
