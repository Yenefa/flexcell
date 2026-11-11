#!/usr/bin/env python3
"""Prove the snapshot tool refuses, using synthetic ROS images and no simulator.

WHY A PROBE AND NOT JUST UNIT TESTS
    The unit tests call accept_message() directly. That proves the ACCEPTANCE
    RULE, not the tool: an exit code is produced by main(), after rclpy has been
    initialised, after a real subscription matched a real publisher. This probe
    exercises that whole path with a hand-built publisher, so the exit codes in
    the report come from the shipped executable.

WHY IT NEEDS NO GAZEBO
    The failure this probe measures is "the tool refuses when it should". A real
    renderer is not needed to show that a truncated buffer or a silent topic is
    rejected - and using one would put a second high-load sim next to the
    running batch for no added evidence.

Modes:
    silent    publish nothing; the tool must exit 2 (no frame)
    truncated publish a frame whose data is shorter than its geometry; exit 3
    uniform   publish an all-zero frame; exit 4
    good      publish a real-looking frame; exit 0 (the positive control)
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time

SNAP = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', '..', 'wt-comp', 'src', 'flexcell', 'flexcell_skills',
    'flexcell_skills', 'camera_snapshot.py')


def make_image(width, height, encoding='rgb8', mode='good'):
    from sensor_msgs.msg import Image
    message = Image()
    message.width, message.height = width, height
    message.step = width * 3
    message.encoding = encoding
    message.header.frame_id = 'probe_camera_link'
    total = message.step * height
    if mode == 'uniform':
        payload = bytes(total)
    elif mode == 'truncated':
        payload = bytes((i * 7) % 251 + 1 for i in range(total))[:-5]
    else:
        payload = bytes((i * 7) % 251 + 1 for i in range(total))
    message.data = payload
    return message


def publisher(topic, mode, count=3, interval=0.2):
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
    from sensor_msgs.msg import Image

    rclpy.init()
    node = Node('vis_failure_probe_pub')
    qos = QoSProfile(depth=5, history=HistoryPolicy.KEEP_LAST,
                     reliability=ReliabilityPolicy.BEST_EFFORT)
    pub = node.create_publisher(Image, topic, qos)
    message = make_image(64, 48, mode=mode)
    stop = threading.Event()

    def spin():
        while not stop.is_set():
            node.get_clock().now()
            message.header.stamp = node.get_clock().now().to_msg()
            pub.publish(message)
            time.sleep(interval)

    thread = threading.Thread(target=spin, daemon=True)
    thread.start()
    return node, stop, thread


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('silent', 'truncated', 'uniform', 'good'))
    parser.add_argument('--topic', default='/flexcell/camera/rgb')
    parser.add_argument('--out', default='/tmp/vis_probe/frame.png')
    parser.add_argument('--timeout', type=float, default=3.0)
    args = parser.parse_args(argv)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    for stale in (args.out, args.out + '.json'):
        if os.path.exists(stale):
            os.remove(stale)

    node = stop = thread = None
    if args.mode != 'silent':
        node, stop, thread = publisher(args.topic, args.mode)

    command = [sys.executable, SNAP, '--out', args.out, '--topic', args.topic,
               '--timeout', str(args.timeout), '--label', 'probe_' + args.mode]
    completed = subprocess.run(command, capture_output=True, text=True)
    wrote_file = os.path.exists(args.out)

    if stop is not None:
        stop.set()
        thread.join(timeout=2.0)
        node.destroy_node()
        import rclpy
        if rclpy.ok():
            rclpy.shutdown()

    report = dict(mode=args.mode, exit_code=completed.returncode,
                  wrote_image=wrote_file,
                  stdout=completed.stdout.strip()[:400],
                  stderr=completed.stderr.strip()[:400])
    print(json.dumps(report, indent=2))

    # The probe's own contract: a refusal must not leave an image behind.
    expected = {'silent': 2, 'truncated': 3, 'uniform': 4, 'good': 0}[args.mode]
    ok = completed.returncode == expected
    if expected != 0 and wrote_file:
        ok = False
        report['violation'] = 'refused but still wrote an image file'
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
