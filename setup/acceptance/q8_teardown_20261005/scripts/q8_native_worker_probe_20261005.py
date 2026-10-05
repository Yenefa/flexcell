"""Native stack instrumentation for a read-only worker, preserving SIGABRT."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

evidence = Path('/home/ros/agentic_workcell_ws/setup/acceptance/q8_pilot_20261005')
environment = dict(os.environ, LD_PRELOAD='/tmp/q8_native_20261005/abort_trace.so',
                   PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION='python')
rows = []
for run in range(1, 11):
    log_path = evidence / ('native_worker_%02d.log' % run)
    with log_path.open('w') as errors:
        worker = subprocess.Popen([sys.executable, '-m', 'flexcell_skills.pose_stream_worker'],
            stdout=subprocess.PIPE, stderr=errors, text=True, env=environment)
        packets = []
        def drain():
            for line in worker.stdout:
                packets.append(line)
        reader = threading.Thread(target=drain)
        reader.start()
        deadline = time.monotonic() + 5
        while not packets and worker.poll() is None and time.monotonic() < deadline:
            time.sleep(.05)
        time.sleep(.5)
        worker.terminate()
        try:
            code = worker.wait(timeout=5)
        except subprocess.TimeoutExpired:
            worker.kill()
            code = worker.wait()
        reader.join(2)
        worker.stdout.close()
    row = dict(run=run, worker_rc=code, received_packets=len(packets), stderr=str(log_path))
    rows.append(row)
    print(json.dumps(row), flush=True)
    if code != 0:
        print(log_path.read_text(), flush=True)
        break
(evidence / 'native_worker_probe.json').write_text(json.dumps(rows, indent=2) + '\n')
