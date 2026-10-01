#!/usr/bin/env python3
"""Bounded native callback control; preserves child exit and stream errors."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time


def child():
    import gz.transport13 as transport
    from gz.msgs10.pose_v_pb2 import Pose_V
    from google.protobuf.internal import api_implementation
    node=transport.Node()
    counts={'messages':0, 'errors':0, 'last_error':''}
    done=threading.Event()
    def receive(msg):
        try:
            _=[p.name for p in msg.pose]
            counts['messages']+=1
        except Exception as exc:
            counts['errors']+=1
            counts['last_error']=repr(exc)
        if counts['messages']+counts['errors']>=100:
            done.set()
    topic='/world/empty/dynamic_pose/info'
    node.subscribe(Pose_V, topic, receive)
    done.wait(8)
    node.unsubscribe(topic)
    print(json.dumps(dict(counts, protobuf=api_implementation.Type())), flush=True)
    return 0 if counts['messages'] and not counts['errors'] else 1


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--child', action='store_true')
    ap.add_argument('--out', type=Path)
    args=ap.parse_args()
    if args.child: return child()
    rows=[]
    for implementation in ('cpp', 'python'):
        for index in range(3):
            env=dict(os.environ, PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=implementation)
            result=subprocess.run([sys.executable, __file__, '--child'], env=env,
                                  capture_output=True, text=True, timeout=25)
            row=dict(implementation=implementation, iteration=index+1, rc=result.returncode,
                     stdout=result.stdout, stderr=result.stderr)
            rows.append(row)
            print(json.dumps(row), flush=True)
    if args.out: args.out.write_text(json.dumps(rows, indent=2)+'\n')
    return 0 if all(r['rc']==0 for r in rows) else 1


if __name__=='__main__':
    raise SystemExit(main())
