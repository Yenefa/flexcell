#!/usr/bin/env python3
"""Probe gz Node.request for the set_pose service."""
import time
import gz.transport13 as gz_transport
from gz.msgs10 import pose_pb2, boolean_pb2
import inspect

node = gz_transport.Node()
print('request sig:', inspect.signature(node.request) if hasattr(inspect, 'signature') else 'n/a')

req = pose_pb2.Pose()
req.name = 'target_box'
req.position.x = 0.22
req.position.y = 0.0
req.position.z = 0.30
req.orientation.w = 1.0
print('req built:', req.name, req.position.z)

rep = boolean_pb2.Boolean()
try:
    result = node.request('/world/empty/set_pose', req, pose_pb2.Pose,
                          boolean_pb2.Boolean, 1000)
    print('request returned:', result)
except Exception as exc:
    print('request raised:', repr(exc))

time.sleep(1.0)
print('PROBE2_OK')
