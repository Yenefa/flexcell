"""Compare a stalled native RPC process with a fresh one on the same service."""
import json
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
    for timeout_ms in (1000, 1000, 1000):
        started = time.monotonic()
        ok, response = node.request('/world/empty/set_pose', req, pose_pb2.Pose,
                                    boolean_pb2.Boolean, timeout_ms)
        print(json.dumps(dict(ok=ok, response_data=response.data,
                              elapsed_s=time.monotonic()-started)), flush=True)
    command = sys.stdin.readline()
    if command.strip() == 'long':
        started = time.monotonic()
        ok, response = Node().request('/world/empty/set_pose', req, pose_pb2.Pose,
                                     boolean_pb2.Boolean, 15000)
        print(json.dumps(dict(ok=ok, response_data=response.data,
                              new_node_same_process=True,
                              elapsed_s=time.monotonic()-started)), flush=True)
    sys.exit(0)

root = Path('/home/ros/agentic_workcell_ws/setup/acceptance/q8_teardown_20261005')
rows = []
found = False
for run in range(1, 51):
    child = subprocess.Popen([sys.executable, __file__, '--child'], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    replies = [json.loads(child.stdout.readline()) for _ in range(3)]
    row = dict(run=run, pid=child.pid, replies=replies)
    if not any(reply['ok'] for reply in replies):
        control = subprocess.Popen([sys.executable, __file__, '--child'], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        row['fresh_process_replies'] = [json.loads(control.stdout.readline()) for _ in range(3)]
        control.stdin.write('stop\n'); control.stdin.flush()
        _, stderr = control.communicate(timeout=5)
        row.update(fresh_rc=control.returncode, fresh_stderr=stderr)
        child.stdin.write('long\n'); child.stdin.flush()
        row['long_same_process_reply'] = json.loads(child.stdout.readline())
        found = True
    else:
        child.stdin.write('stop\n'); child.stdin.flush()
    _, stderr = child.communicate(timeout=5)
    row.update(rc=child.returncode, stderr=stderr)
    rows.append(row)
    print(json.dumps(row), flush=True)
    (root / 'rpc_process_control.json').write_text(json.dumps(dict(found_stalled_process=found, rows=rows), indent=2)+'\n')
    if found:
        break
