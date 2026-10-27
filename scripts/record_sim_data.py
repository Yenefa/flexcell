#!/usr/bin/env python3
"""Record one RGB stream plus causal state/controller targets; never commands a robot.

ROS/system NumPy environment only. LeRobot conversion runs in a separate venv.
Raw rosbag, rejected frames, original timestamps and physics traces are retained.
"""
import argparse
from collections import deque
import json
from pathlib import Path
import signal
import struct
import subprocess
import threading
import time
import zlib

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, qos_profile_sensor_data
from rclpy.signals import SignalHandlerOptions
from sensor_msgs.msg import Image, JointState
from control_msgs.msg import JointTrajectoryControllerState
from std_msgs.msg import String

JOINTS = ['joint1', 'joint2', 'joint3', 'joint4', 'gripper_left_joint']
TOPICS = ['/clock', '/tf', '/tf_static', '/joint_states', '/arm_controller/controller_state',
          '/flexcell/execution_command', '/flexcell/camera/rgb', '/flexcell/camera/rgb/camera_info',
          '/flexcell/physics_trace', '/flexcell/carry_state', '/flexcell/task_state']


def stamp_ns(header):
    return header.stamp.sec * 10**9 + header.stamp.nanosec


def causal(history, stamp, max_age_ns):
    choices = [entry for entry in history if entry['sim_ns'] <= stamp]
    if not choices:
        return None
    entry = max(choices, key=lambda item: item['sim_ns'])
    return entry if stamp - entry['sim_ns'] <= max_age_ns else None


def write_png(path, msg):
    channels = {'rgb8': 3, 'bgr8': 3, 'rgba8': 4, 'bgra8': 4}.get(msg.encoding)
    if channels is None or msg.width != 640 or msg.height != 480:
        raise ValueError('expected 640x480 RGB-compatible sensor image')
    pixels = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.step)
    pixels = pixels[:, :msg.width * channels].reshape(msg.height, msg.width, channels)[:, :, :3]
    if msg.encoding.startswith('bgr'):
        pixels = pixels[:, :, ::-1]
    raw = b''.join(b'\x00' + row.tobytes() for row in pixels)
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    content = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', msg.width, msg.height, 8, 2, 0, 0, 0))
               + chunk(b'IDAT', zlib.compress(raw, 3)) + chunk(b'IEND', b''))
    with path.open('xb') as stream:
        stream.write(content)


class Recorder(Node):
    def __init__(self, out):
        super().__init__('flexcell_data_recorder', parameter_overrides=[
            rclpy.parameter.Parameter('use_sim_time', value=True)])
        self.out, self.states, self.references, self.gripper = out, deque(maxlen=500), deque(maxlen=500), deque(maxlen=100)
        self.frames = (out / 'frames.jsonl').open('x')
        self.physics = (out / 'physics.jsonl').open('x')
        self.index, self.valid, self.last, self.errors = 0, 0, -1, []
        (out / 'images').mkdir()
        self.create_subscription(JointState, '/joint_states', self.state, qos_profile_sensor_data)
        self.create_subscription(JointTrajectoryControllerState, '/arm_controller/controller_state',
                                 self.reference, qos_profile_sensor_data)
        self.create_subscription(String, '/flexcell/execution_command', self.command,
            QoSProfile(depth=10, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.create_subscription(String, '/flexcell/physics_trace', self.trace, 100)
        self.create_subscription(Image, '/flexcell/camera/rgb', self.frame, qos_profile_sensor_data)

    def state(self, msg):
        self.states.append(dict(sim_ns=stamp_ns(msg.header), positions=dict(zip(msg.name, msg.position))))

    def reference(self, msg):
        self.references.append(dict(sim_ns=stamp_ns(msg.header),
                                    positions=dict(zip(msg.joint_names, msg.reference.positions))))

    def command(self, msg):
        try:
            data = json.loads(msg.data)
            if data['kind'] == 'gripper_position_target' and data['accepted'] is True:
                self.gripper.append(data)
        except (ValueError, KeyError) as exc:
            self.errors.append(str(exc))

    def trace(self, msg):
        try:
            data = json.loads(msg.data)
            if data['schema_version'] != 1 or data['sim_ns'] < 0:
                raise ValueError('invalid physics trace')
            self.physics.write(json.dumps(data, allow_nan=False) + '\n')
            self.physics.flush()
        except (ValueError, KeyError) as exc:
            self.errors.append(str(exc))

    def frame(self, msg):
        stamp = stamp_ns(msg.header)
        row = dict(frame_index=self.index, sim_ns=stamp, monotonic_ns=time.monotonic_ns(),
                   image='images/%06d.png' % self.index, valid=False, reasons=[])
        self.index += 1
        try:
            write_png(self.out / row['image'], msg)
            if stamp <= self.last:
                row['reasons'].append('nonmonotonic_camera_stamp')
            self.last = stamp
            state = causal(self.states, stamp, 50_000_000)
            reference = causal(self.references, stamp, 50_000_000)
            # A gripper position target persists until the next accepted command.
            gripper = causal(self.gripper, stamp, 600_000_000_000)
            for name, value in [('state', state), ('controller_reference', reference), ('gripper_target', gripper)]:
                row[name] = value
                if value is None:
                    row['reasons'].append('missing_or_stale_' + name)
            if state is not None and reference is not None and gripper is not None:
                row['observation.state'] = [state['positions'].get(n) for n in JOINTS]
                row['action'] = [reference['positions'].get(n) for n in JOINTS[:4]] + [gripper['position']]
                if any(v is None or not np.isfinite(v) for v in row['observation.state'] + row['action']):
                    row['reasons'].append('incomplete_or_nonfinite_joints')
            row['valid'] = not row['reasons']
            self.valid += int(row['valid'])
        except (ValueError, OSError, KeyError) as exc:
            row['reasons'].append(str(exc))
        self.frames.write(json.dumps(row, allow_nan=False) + '\n')
        self.frames.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--camera', action='store_true', help='Require aligned RGB frames in this recording')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = Recorder(args.out)
    log = (args.out / 'rosbag.log').open('x')
    bag = subprocess.Popen(['ros2', 'bag', 'record', '--storage', 'sqlite3', '--output',
                            str(args.out / 'raw'), *TOPICS], stdout=log, stderr=subprocess.STDOUT,
                           start_new_session=True)
    try:
        while not stop.is_set():
            rclpy.spin_once(node, timeout_sec=.1)
            if bag.poll() is not None:
                raise RuntimeError('raw rosbag recorder exited before collection completed')
    finally:
        if bag.poll() is None:
            import os
            os.killpg(bag.pid, signal.SIGINT)
            try:
                bag.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(bag.pid, signal.SIGTERM)
                bag.wait(timeout=5)
        node.frames.close(); node.physics.close(); log.close()
        (args.out / 'collection.json').write_text(json.dumps(dict(
            schema_version=1, frames=node.index, valid_frames=node.valid, errors=node.errors,
            rosbag_exit=bag.returncode, joints=JOINTS,
            action_semantics='arm controller reference positions + held accepted gripper position target',
            synchronization='causal source stamps; state/reference age <=50ms; no interpolation',
            observation_source='SIMULATION_GROUND_TRUTH; camera is data-only'), indent=2) + '\n')
        node.destroy_node(); rclpy.shutdown()
    return 0 if (not args.camera or node.valid > 0) and not node.errors and bag.returncode == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
