#!/usr/bin/env python3
"""Bounded readiness through a fresh ROS participant, without the ROS CLI."""
import argparse
import json
import time

import rclpy
from rclpy.action import get_action_names_and_types
from rclpy.node import Node
from controller_manager_msgs.srv import ListControllers

CONTROLLERS = ('arm_controller', 'gripper_controller', 'joint_state_broadcaster')
NODES = {'move_to_pose_server', 'observe_server', 'pick_server', 'place_server',
         'verify_server', 'task_fsm_server', 'carry_server', 'move_group',
         'robot_state_publisher', 'rviz2'}
ACTIONS = {'/move_to_pose', '/observe', '/pick_object', '/place_object',
           '/verify_object', '/run_demo', '/run_pick_place'}


def controllers(node, deadline):
    client = node.create_client(ListControllers, '/controller_manager/list_controllers')
    states, reason = {}, 'service unavailable'
    try:
        while time.monotonic() < deadline:
            if not client.wait_for_service(timeout_sec=min(1., max(0., deadline-time.monotonic()))):
                continue
            future = client.call_async(ListControllers.Request())
            rclpy.spin_until_future_complete(node, future, timeout_sec=min(3., max(0., deadline-time.monotonic())))
            if future.done() and future.result() is not None:
                states = {c.name: c.state for c in future.result().controller}
                if all(states.get(name) == 'active' for name in CONTROLLERS):
                    return {'ok': True, 'controllers': states}
                reason = 'required controllers are not all active'
            else:
                reason = 'ListControllers response timed out'
                client.remove_pending_request(future)
            rclpy.spin_once(node, timeout_sec=min(.2, max(0., deadline-time.monotonic())))
        return {'ok': False, 'controllers': states, 'error': reason}
    finally:
        node.destroy_client(client)


def stopped(node, deadline):
    nodes, actions = [], []
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=.2)
        nodes = sorted(n for n in node.get_node_names() if n in NODES)
        actions = sorted(n for n, _ in get_action_names_and_types(node) if n in ACTIONS)
        # Give the fresh participant time to discover surviving peers.
        if time.monotonic() > deadline-2 and not nodes and not actions:
            return {'ok': True, 'nodes': [], 'actions': []}
    return {'ok': not nodes and not actions, 'nodes': nodes, 'actions': actions}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=('controllers', 'stopped'))
    ap.add_argument('--timeout', type=float, default=10.)
    args = ap.parse_args()
    if not 0 < args.timeout <= 120:
        ap.error('timeout must be in (0,120]')
    rclpy.init()
    node = Node('flexcell_lifecycle_probe')
    try:
        report = globals()[args.mode](node, time.monotonic()+args.timeout)
        print(json.dumps(report))
        return 0 if report['ok'] else 1
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
