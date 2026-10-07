#!/usr/bin/env bash
set -e
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
python3 - <<'PY'
import json,time,os
from pathlib import Path
import rclpy
from rclpy.qos import QoSProfile,QoSReliabilityPolicy,QoSDurabilityPolicy
from std_msgs.msg import String
from flexcell_skills.confidence_calibration import ConfidenceCalibration,prompt_digest
from flexcell_skills.jev_policy import JevPolicy
from flexcell_skills.jev_backends import make_backend
c=ConfidenceCalibration();assert c.error=='' and JevPolicy(make_backend('clef')).route_eligible(.85)
assert c.sha256=='34eac55fcfdda978286df25b3f6a13f4047e4ca9002ec829d83f262073215f0c'
assert prompt_digest()=='b37e71cd0b9b0ff81cfa3638111da8375251be2fadeabc01468ce46b5f4e85b8'
rclpy.init();node=rclpy.create_node('composite_postflight');seen=[]
qos=QoSProfile(depth=1,reliability=QoSReliabilityPolicy.RELIABLE,durability=QoSDurabilityPolicy.TRANSIENT_LOCAL)
node.create_subscription(String,'/flexcell/task_state',lambda m:seen.append(m.data),qos)
end=time.monotonic()+12
while not seen and time.monotonic()<end:rclpy.spin_once(node,timeout_sec=.1)
node.destroy_node();rclpy.shutdown();assert seen and seen[-1]=='IDLE',seen
record=dict(ok=True,task_state=seen[-1],calibration_sha256=c.sha256,prompt_sha256=prompt_digest(),route_eligible_085=True,ros_domain_id=int(os.environ['ROS_DOMAIN_ID']))
with Path('setup/acceptance/composite_resume_20261007/validation/postflight.json').open('x') as f:json.dump(record,f,indent=2)
print(json.dumps(record))
PY
