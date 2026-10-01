"""Owned, isolated Gazebo subscriber. No native callbacks in the ROS process."""
import argparse
import json
import os
import signal
import threading
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--world', default='empty')
    args = ap.parse_args()
    import gz.transport13 as transport
    from gz.msgs10.pose_v_pb2 import Pose_V
    node = transport.Node()
    stop = threading.Event()
    lock = threading.Lock()
    last = 0.
    errors = 0

    def receive(raw, _info):
        nonlocal last, errors
        now = time.monotonic()
        with lock:
            if now-last < .05 or stop.is_set():
                return
            last = now
            try:
                msg = Pose_V()
                msg.ParseFromString(raw)
                poses = {p.name: [[p.position.x, p.position.y, p.position.z],
                                 [p.orientation.x, p.orientation.y, p.orientation.z,
                                  p.orientation.w], now] for p in msg.pose}
                print(json.dumps({'poses': poses, 'mono': now, 'cb_errors': errors}), flush=True)
            except BrokenPipeError:
                stop.set()
            except Exception as exc:
                errors += 1
                print(json.dumps({'error': type(exc).__name__, 'cb_errors': errors}), flush=True)

    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    topic = '/world/%s/dynamic_pose/info' % args.world
    options = transport.SubscribeOptions()
    options.msgs_per_sec = 20  # bound native-to-Python traffic before decoding
    if not node.subscribe_raw(topic, receive, Pose_V.DESCRIPTOR.full_name, options):
        raise RuntimeError('Gazebo raw subscription refused')
    owner = os.getppid()
    while not stop.wait(.2):
        if os.getppid() != owner:  # parent death, including SIGKILL/SIGSEGV
            stop.set()
    node.unsubscribe(topic)


if __name__ == '__main__':
    main()
