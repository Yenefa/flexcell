"""Preserve stdout, stderr, payload and process exit for every real reset."""
import json
from pathlib import Path
import subprocess
import sys
import time

evidence = Path(sys.argv[1])
rows = []
for run in range(1, 21):
    started = time.monotonic()
    proc = subprocess.run([sys.executable, '/home/ros/agentic_workcell_ws/setup/flexcell_admin.py', 'reset'],
                          capture_output=True, text=True, timeout=120)
    (evidence / ('reset_%02d.stdout.log' % run)).write_text(proc.stdout)
    (evidence / ('reset_%02d.stderr.log' % run)).write_text(proc.stderr)
    payload = None
    for index, char in enumerate(proc.stdout):
        if char != '{':
            continue
        try:
            value, _ = json.JSONDecoder().raw_decode(proc.stdout[index:])
            if isinstance(value, dict) and 'ok' in value:
                payload = value
                break
        except ValueError:
            pass
    row = dict(run=run, process_rc=proc.returncode, payload=payload,
               elapsed_s=time.monotonic() - started,
               ok=proc.returncode == 0 and payload is not None and payload.get('ok') is True)
    rows.append(row)
    (evidence / 'reset20.json').write_text(json.dumps(rows, indent=2) + '\n')
    print(json.dumps(dict(run=run, rc=proc.returncode, ok=row['ok'], elapsed_s=row['elapsed_s'])), flush=True)
    if not row['ok']:
        print(proc.stdout, proc.stderr, flush=True)
        break
sys.exit(0 if len(rows) == 20 and all(row['ok'] for row in rows) else 1)
