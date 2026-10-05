"""Owned, isolated Gazebo subscriber. No native callbacks in the ROS process."""
import argparse
import json
import os
import signal
import threading
import time
import weakref


def _unsubscribe_and_wait(node, topic, released, timeout_s=3.):
    """Wait for the transport to drop every Python callback reference."""
    if not node.unsubscribe(topic):
        raise RuntimeError('Gazebo pose unsubscribe refused')
    if not released.wait(timeout_s):
        raise RuntimeError('Gazebo pose callback was not released before shutdown')


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
    # Transport 13.6 may retain an in-flight RawSubscriptionHandler after
    # unsubscribe returns. Its destructor acquires the GIL to release receive;
    # doing that during Py_FinalizeEx aborts the native reception thread. Let
    # transport own the only callback reference, then observe its final release.
    released = threading.Event()
    weakref.finalize(receive, released.set)
    del receive
    owner = os.getppid()
    while not stop.wait(.2):
        if os.getppid() != owner:  # parent death, including SIGKILL/SIGSEGV
            stop.set()
    _unsubscribe_and_wait(node, topic, released)


if __name__ == '__main__':
    main()
