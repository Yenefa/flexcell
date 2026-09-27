#!/usr/bin/env python3
"""Probe gz-transport python publisher API + Empty message availability."""
import gz.transport13 as gz_transport
print('Node methods:', [m for m in dir(gz_transport.Node) if not m.startswith('_')])

from gz.msgs10 import empty_pb2
print('Empty type:', empty_pb2.Empty)
e = empty_pb2.Empty()
print('Empty instance ok:', e)

node = gz_transport.Node()
pub = node.advertise('/flexcell/target_box/attach', e)
print('advertise returned:', pub)
r = pub.publish(e)
print('publish returned:', r)

# give discovery a moment, then verify delivery by re-publishing after delay
import time
time.sleep(1.0)
print('second publish:', pub.publish(e))
print('PROBE_OK')
