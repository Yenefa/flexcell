#!/usr/bin/env python3
"""Find the importable Empty class with a DESCRIPTOR for gz-transport subscribe."""
import gz.msgs10 as m
print('type(m.Empty):', type(getattr(m, 'Empty', None)))
for cand in ('Empty', 'empty_pb2'):
    obj = getattr(m, cand, None)
    print(cand, '->', obj)

from gz.msgs10 import empty_pb2
import inspect
print('empty_pb2.Empty is:', type(empty_pb2.Empty))
print('module file:', empty_pb2.__file__)
print('module names:', [n for n in dir(empty_pb2) if not n.startswith('_')][:10])

# the shim likely wraps the real class - look at gz.msgs namespace too
import gz.msgs as mm
print('gz.msgs Empty:', type(getattr(mm, 'Empty', None)))
obj = getattr(mm, 'Empty', None)
if obj is not None and hasattr(obj, 'DESCRIPTOR'):
    print('USE gz.msgs.Empty - DESCRIPTOR:', obj.DESCRIPTOR.full_name)
