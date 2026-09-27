#!/usr/bin/env bash
# Listener test: does the AttachGate publish actually ARRIVE on the gz topic?
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
cd /home/ros/agentic_workcell_ws

python3 <<'EOF' > /tmp/w1_listener.out 2>&1 &
import time
import gz.transport13 as gz_transport
from gz.msgs10 import empty_pb2

received = []
def cb(msg, info):
    received.append(time.time())
    print('RECEIVED Empty at %.2f' % time.time(), flush=True)

node = gz_transport.Node()
node.subscribe(cb, '/flexcell/target_box/attach', empty_pb2.Empty)
print('listener up', flush=True)
time.sleep(45)
print('total received: %d' % len(received), flush=True)
EOF
LPID=$!
sleep 5
echo "=== run solo task (pick publishes 2x) ==="
timeout 120 python3 src/flexcell/flexcell_skills/test/w1_client.py --action task --object target_box --pose 0.12 -0.15 0.0175 2>&1 | tail -8
sleep 2
echo "=== listener saw ==="
cat /tmp/w1_listener.out
kill $LPID 2>/dev/null
echo "LISTEN_DONE"
