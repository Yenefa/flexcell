"""Read-only subscriber lifecycle probe; stops at the first abnormal exit."""
import json
import os
from pathlib import Path
import sys
import time

from flexcell_skills.common import (_ensure_gz_pose_stream, _GZ_STREAM,
                                   gz_stream_health, stop_gz_pose_stream)

rows = []
if '--native' in sys.argv:
    os.environ['LD_PRELOAD'] = '/tmp/q8_native_20261005/abort_trace.so'
for run in range(1, 21):
    _ensure_gz_pose_stream()
    time.sleep(.5)
    with _GZ_STREAM['lock']:
        last_rx = _GZ_STREAM['last_rx']
        worker_pid = _GZ_STREAM['worker'].pid
    row = dict(run=run, received_pose=last_rx > 0, worker_pid=worker_pid)
    try:
        stop_gz_pose_stream()
        row['ok'] = True
    except Exception as exc:
        row.update(ok=False, error=str(exc))
    with _GZ_STREAM['lock']:
        row.update(worker_rc=_GZ_STREAM.get('worker_rc'),
                   native_stderr_tail=_GZ_STREAM['cb_error'])
    rows.append(row)
    print(json.dumps(row), flush=True)
    native_trace = Path('/tmp/q8_native_20261005/backtrace_%d.log' % worker_pid)
    if '--native' in sys.argv and native_trace.exists() and native_trace.stat().st_size:
        target = Path(sys.argv[1]).parent / ('native_backtrace_%d.log' % worker_pid)
        target.write_bytes(native_trace.read_bytes())
        print(target.read_text(), flush=True)
    if not row['ok']:
        break
Path(sys.argv[1]).write_text(json.dumps(dict(read_only=True, rows=rows), indent=2) + '\n')
sys.exit(0 if all(row['ok'] for row in rows) else 1)
