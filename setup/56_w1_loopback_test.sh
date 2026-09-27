#!/usr/bin/env bash
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
cd /home/ros/agentic_workcell_ws
C=src/flexcell/flexcell_skills/test/move_to_pose_client.py

echo "=== TEST A: same-process loopback ==="
python3 <<'EOF'
import time
import gz.transport13 as gz_transport
from gz.msgs10 import empty_pb2

got = []
def cb(msg, info):
    got.append(1)
    print('LOOPBACK RECEIVED', flush=True)

node = gz_transport.Node()
Empty = empty_pb2.Empty
node.subscribe(cb, '/flexcell/loopback', Empty)
time.sleep(1.0)
pub = node.advertise('/flexcell/loopback', Empty())
time.sleep(1.0)
pub.publish(Empty())
time.sleep(1.0)
print('loopback count:', len(got), flush=True)
EOF

echo "=== TEST B: python publisher, warm 3s, publish once, then move arm ==="
python3 <<'EOF' &
import time
import gz.transport13 as gz_transport
from gz.msgs10 import empty_pb2
node = gz_transport.Node()
Empty = empty_pb2.Empty
pub = node.advertise('/flexcell/target_box/attach', Empty())
time.sleep(3.0)
print('publish result:', pub.publish(Empty()), flush=True)
time.sleep(2.0)
EOF
BPID=$!
sleep 6
echo "--- arm move (0.20,0.05,0.24 -> 0.15,-0.10,0.28) ---"
timeout 60 python3 $C --pose 0.15 -0.10 0.28 0 0 0 1 --request-id isoB 2>&1 | grep -E '"outcome"' | head -1
sleep 1
echo "--- box after (moved => ATTACH worked) ---"
timeout 10 gz model -m target_box -p 2>/dev/null | grep -A1 XYZ | head -2
wait $BPID
echo "=== publish once more (detach) + box should drop ==="
python3 <<'EOF'
import time
import gz.transport13 as gz_transport
from gz.msgs10 import empty_pb2
node = gz_transport.Node()
pub = node.advertise('/flexcell/target_box/attach', empty_pb2.Empty())
time.sleep(3.0)
pub.publish(empty_pb2.Empty())
time.sleep(1.0)
EOF
sleep 2
timeout 10 gz model -m target_box -p 2>/dev/null | grep -A1 XYZ | head -2
echo "TESTAB_DONE"
