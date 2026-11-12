"""Synthetic ROS protocol/safety checks. No Gazebo or physical evidence."""
import json
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

import rclpy
from rclpy.action import ActionServer, CancelResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import JointState
from flexcell_interfaces.action import Observe, PushObject
from flexcell_interfaces.msg import WorldObject, WorldState


class Fixture(Node):
    def __init__(self):
        super().__init__('SYNTHETIC_feedback_instrument_test')
        self.x = .22
        self.calls = []
        self.velocities = True
        self.slow = False
        self.started = threading.Event()
        group = ReentrantCallbackGroup()
        self.joints = self.create_publisher(JointState, '/joint_states', 100)
        self.timer = self.create_timer(.02, self.publish_joints, callback_group=group)
        self.observer = ActionServer(self, Observe, '/observe', self.observe, callback_group=group)
        self.pusher = ActionServer(self, PushObject, '/push_object', self.push,
                                  callback_group=group, cancel_callback=lambda _: CancelResponse.ACCEPT)

    def publish_joints(self):
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = ['joint1', 'joint2', 'joint3', 'joint4']
        msg.position = [0.] * 4
        msg.velocity = [0.] * 4 if self.velocities else []
        self.joints.publish(msg)

    def observe(self, handle):
        world = WorldState()
        world.header.stamp = self.get_clock().now().to_msg()
        world.header.frame_id = 'world'
        world.source = 'SIMULATION_GROUND_TRUTH'  # Protocol fixture, NOT actual physics.
        world.schema_version = '2.0'
        world.robot.has_gripper_state = True
        world.robot.gripper_joint_name = 'gripper_left_joint'
        world.robot.ee_frame = 'end_effector_link'
        world.robot.ee_pose.orientation.w = 1.
        world.notes = ['SYNTHETIC protocol fixture; no robot evidence']
        for name, pos in [('target_box_a', [self.x, 0., .0175]), ('target_box_b', [.2, -.18, .0175])]:
            obj = WorldObject()
            obj.name = name
            obj.available = True
            obj.pose_age_s = .01
            obj.pose.position.x, obj.pose.position.y, obj.pose.position.z = pos
            obj.pose.orientation.w = 1.
            world.objects.append(obj)
        result = Observe.Result()
        result.world_state = world
        handle.succeed()
        return result

    def push(self, handle):
        g = handle.request
        self.calls.append(dict(distance=g.distance_m, overdrive=g.overdrive_m,
                               increments=g.max_increments))
        self.started.set()
        if self.slow:
            end = time.monotonic() + 5
            while not handle.is_cancel_requested and time.monotonic() < end:
                time.sleep(.01)
        result = PushObject.Result()
        if handle.is_cancel_requested:
            result.outcome = 2
            result.error_code = 32
            handle.canceled()
        else:
            self.x -= .025
            result.contact_made = True
            result.displacement_along_direction_m = .025
            handle.succeed()
        return result


def main():
    root = Path('/candidate')
    out = Path('/artifacts/ros_feedback_checks')
    out.mkdir(exist_ok=False)
    command = [sys.executable, str(root / 'src/flexcell/flexcell_skills/run_push_feedback.py'),
               str(root / 'benchmark/tasks/t08_dev/T08-push-seed2000.json')]
    checks = dict(kind='SYNTHETIC_ROS_CHECKS', physical_evidence=False)
    rclpy.init()
    fixture = Fixture()
    executor = MultiThreadedExecutor(num_threads=3)
    executor.add_node(fixture)
    worker = threading.Thread(target=executor.spin)
    worker.start()
    try:
        for name, velocity in [('positive', True), ('unknown_velocity', False)]:
            fixture.x, fixture.velocities = .22, velocity
            before = len(fixture.calls)
            proc = subprocess.run(command + [str(out/name)], capture_output=True, text=True, timeout=40)
            (out/(name+'.log')).write_text(proc.stdout + proc.stderr)
            summary = json.loads((out/name/'feedback.json').read_text())
            if velocity:
                assert proc.returncode == 0 and summary['status'] == 'GOAL_GEOMETRY_REACHED', summary
                assert summary['attempts'] == 2 and len(fixture.calls)-before == 2
                assert all(abs(c['distance']-.03) < 1e-9 and abs(c['overdrive']-.005) < 1e-9
                           and c['increments'] == 1 for c in fixture.calls)
                checks['post_return_geometry_stops_before_extra_push'] = 'PASS'
                checks['legal_bounded_request_fields'] = 'PASS'
            else:
                assert proc.returncode == 2 and summary['status'] == 'STATE_UNAVAILABLE', summary
                assert len(fixture.calls) == before
                checks['missing_joint_velocity_dispatches_no_push'] = 'PASS'
        fixture.x, fixture.velocities, fixture.slow = .22, True, True
        fixture.started.clear()
        before = len(fixture.calls)
        proc = subprocess.Popen(command + [str(out/'cancel')], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        assert fixture.started.wait(timeout=20)
        proc.send_signal(signal.SIGINT)
        output, _ = proc.communicate(timeout=20)
        (out/'cancel.log').write_text(output)
        summary = json.loads((out/'cancel/feedback.json').read_text())
        assert summary['status'] == 'CANCELED', summary
        assert len(fixture.calls) == before+1
        checks['cancel_forwards_and_dispatches_no_next_shot'] = 'PASS'
    finally:
        executor.shutdown(timeout_sec=3.)
        worker.join(timeout=3.)
        fixture.destroy_node()
        rclpy.shutdown()
        (out/'checks.json').write_text(json.dumps(checks, indent=2)+'\n')
    print(json.dumps(checks))


if __name__ == '__main__':
    main()
