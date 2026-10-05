"""Cold Gazebo RPC control: preserve transport result and response data."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

if '--child' in sys.argv:
    from gz.msgs10 import boolean_pb2, pose_pb2
    from gz.transport13 import Node
    node = Node()
    req = pose_pb2.Pose()
    req.name = 'target_box_a'
    req.position.x, req.position.y, req.position.z = .22, 0., .0175
    req.orientation.w = 1.
    rows = []
    for attempt in range(1, 4):
        started = time.monotonic()
        ok, response = node.request('/world/empty/set_pose', req, pose_pb2.Pose,
                                    boolean_pb2.Boolean, int(sys.argv[-1]))
        rows.append(dict(attempt=attempt, ok=ok, response_data=response.data,
                         elapsed_s=time.monotonic() - started))
    print(json.dumps(rows))
    sys.exit(0)

root = Path('/home/ros/agentic_workcell_ws/setup/acceptance/q8_teardown_20261005')
rows = []
for timeout_ms in (1000, 3000):
    for run in range(1, 11):
        proc = subprocess.run([sys.executable, __file__, '--child', str(timeout_ms)],
                              capture_output=True, text=True, timeout=20)
        row = dict(timeout_ms=timeout_ms, run=run, rc=proc.returncode,
                   responses=json.loads(proc.stdout) if proc.returncode == 0 else None,
                   stderr=proc.stderr)
        rows.append(row)
        print(json.dumps(row), flush=True)
        (root / 'reset_rpc_cold.json').write_text(json.dumps(rows, indent=2) + '\n')
        if proc.returncode != 0:
            sys.exit(1)
