#!/usr/bin/env python3
"""Real ROS/DDS acquisition checks with SYNTHETIC messages, no robot or Gazebo.

Run after sourcing ROS and the compiled flexcell_interfaces package:
  python3 verify_world_state_ros.py /new/evidence/directory
"""

import json
from pathlib import Path
import subprocess
import sys
import threading

import rclpy
from rclpy.action import ActionServer
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSCompatibility, QoSProfile, qos_check_compatible
from flexcell_interfaces.action import Observe
from flexcell_interfaces.msg import WorldObject, WorldState

from record_world_state import issues


class SyntheticObservation(Node):
    def __init__(self):
        super().__init__('synthetic_observation_INSTRUMENT_TEST_ONLY')
        self.publisher = self.create_publisher(WorldState, '/flexcell/world_state', 1)
        self.invalid = False
        self.server = ActionServer(self, Observe, 'observe', self.execute)

    def execute(self, handle):
        world = WorldState()
        world.header.stamp = self.get_clock().now().to_msg()
        world.header.frame_id = 'world'
        world.source = 'SIMULATION_GROUND_TRUTH'  # Fixture protocol field; not actual truth.
        world.schema_version = '2.0'
        world.robot.ee_frame = 'end_effector_link'
        world.robot.ee_pose.orientation.w = 1.
        world.robot.has_gripper_state = True
        world.robot.gripper_joint_name = 'gripper_left_joint'
        for name in ('target_box_a', 'target_box_b'):
            obj = WorldObject()
            obj.name = name
            obj.available = True
            obj.pose.orientation.w = 1.
            obj.pose_age_s = .001
            world.objects.append(obj)
        if self.invalid:
            world.notes = ['ee: lookup failed (synthetic missing TF)']
        self.publisher.publish(world)
        result = Observe.Result()
        result.world_state = world
        handle.succeed()
        return result


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=False)
    recorder = Path(__file__).with_name('record_world_state.py')
    checks = dict(kind='SYNTHETIC_ROS_INSTRUMENT_VERIFICATION', robot_execution=False)
    rclpy.init()
    node = SyntheticObservation()
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    thread = threading.Thread(target=executor.spin)
    thread.start()
    try:
        volatile = QoSProfile(depth=1, durability=DurabilityPolicy.VOLATILE)
        transient = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        assert qos_check_compatible(volatile, transient)[0] == QoSCompatibility.ERROR
        assert qos_check_compatible(transient, volatile)[0] != QoSCompatibility.ERROR
        checks['durability_request_offer_direction'] = 'PASS'

        def run(name, active):
            cmd = [sys.executable, str(recorder), '--out', str(out / name),
                   '--duration', '5', '--observe-period', '.1' if active else '0']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            (out / (name + '.stdout')).write_text(result.stdout)
            (out / (name + '.stderr')).write_text(result.stderr)
            return result.returncode, json.loads((out / name / 'summary.json').read_text())

        code, passive = run('passive', False)
        assert code == 2 and passive['topic_samples'] == 0, passive
        endpoints = [json.loads(line) for line in
                     (out / 'passive/events.jsonl').read_text().splitlines()]
        assert any(event['kind'] == 'PUBLISHERS' and event['endpoints'] for event in endpoints)
        checks['publisher_exists_but_no_event_means_zero_samples'] = 'PASS'

        code, active = run('active', True)
        assert code == 0 and active['topic_samples'] >= 2 and active['result_samples'] >= 2, active
        assert active['errors'] == [], active
        checks['observe_requests_restore_topic_and_result_samples'] = 'PASS'

        records = [json.loads(line) for line in
                   (out / 'active/world_state.jsonl').read_text().splitlines()]
        world = records[0]['world_state']
        assert not issues(world, ['target_box_a', 'target_box_b'])
        world['robot']['has_gripper_state'] = False
        assert issues(world, ['target_box_a'])
        world['robot']['has_gripper_state'] = True
        world['objects'][0]['pose_age_s'] = 2.
        assert issues(world, ['target_box_a'])
        checks['missing_gripper_and_stale_object_not_usable'] = 'PASS'

        node.invalid = True
        code, invalid = run('invalid_tf', True)
        assert code == 2 and invalid['topic_samples'] >= 2, invalid
        assert invalid['usable_topic_samples'] == 0, invalid
        checks['failed_tf_default_pose_is_not_usable'] = 'PASS'

        # The output directory must never be reused, even after a failed capture.
        result = subprocess.run([sys.executable, str(recorder), '--out', str(out / 'passive')],
                                capture_output=True, text=True, timeout=5)
        assert result.returncode != 0
        assert json.loads((out / 'passive/summary.json').read_text()) == passive
        checks['existing_failed_capture_preserved'] = 'PASS'
    finally:
        executor.shutdown(timeout_sec=3.)
        thread.join(timeout=3.)
        node.destroy_node()
        rclpy.shutdown()
        (out / 'checks.json').write_text(json.dumps(checks, indent=2) + '\n')
    print(json.dumps(checks))


if __name__ == '__main__':
    main()
