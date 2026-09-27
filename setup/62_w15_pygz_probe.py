#!/usr/bin/env python3
"""Probe: python gz service call + Pose_V topic subscription (CLI-free paths)."""
import time
import gz.transport13 as gz_transport
from gz.msgs10 import boolean_pb2, pose_pb2, pose_v_pb2

node = gz_transport.Node()

# 1) service call: set A back to canonical (also proves requests work)
req = pose_pb2.Pose()
req.name = 'target_box_a'
req.position.x, req.position.y, req.position.z = 0.22, 0.0, 0.0175
req.orientation.w = 1.0
r = node.request('/world/empty/set_pose', req, pose_pb2.Pose,
                 boolean_pb2.Boolean, 1500)
print('set_pose request:', r)

# 2) subscribe dynamic poses for 2s and capture our objects
got = {}

def cb(msg):
    for ent in msg.entities:
        if ent.name.startswith('target_box'):
            got[ent.name] = (round(ent.position.x, 4), round(ent.position.y, 4),
                             round(ent.position.z, 4))

node.subscribe(type(pose_v_pb2.Pose_V()), '/world/empty/dynamic_pose/info', cb)
t0 = time.time()
while time.time() - t0 < 2.5 and len(got) < 2:
    time.sleep(0.1)
print('observed:', got)
print('PROBE_DONE')
