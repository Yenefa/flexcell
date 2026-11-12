"""Retain raw joint state samples for the existing evidence recorder."""
import json
from pathlib import Path
import sys
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState

out, stop = Path(sys.argv[1]), Path(sys.argv[2])
rclpy.init()
node = Node('reposition_joint_recorder')
with out.open('x') as stream:
    def received(msg):
        stream.write(json.dumps(dict(monotonic_ns=time.monotonic_ns(),
                                     name=list(msg.name), position=list(msg.position)),
                                allow_nan=False) + '\n')
        stream.flush()
    subscription = node.create_subscription(JointState, '/joint_states', received, 100)
    deadline = time.monotonic() + 360
    while rclpy.ok() and not stop.exists() and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=.05)
node.destroy_node()
rclpy.shutdown()
