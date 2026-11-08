#!/usr/bin/env python3
"""One bounded RunComposite chain on a live stack; prints JSON RESULT.

Reviewable probe for the composite runtime unit (U3). It sends a single
declared outer plan and reports the terminal result; it does not retry, does
not score success rates and does not modify any world.

Usage:
  composite_probe.py --object target_box_a --place 0.12 -0.15 0.0175
"""
import argparse
import json
import sys
import time
import uuid

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.executors import SingleThreadedExecutor

from geometry_msgs.msg import Point
from flexcell_interfaces.action import RunComposite
from flexcell_interfaces.msg import CompositeStage, ObjectPosition


def name_of(cls, prefix, value):
    for k, v in vars(cls).items():
        if k.startswith(prefix) and isinstance(v, int) and v == value:
            return k
    return str(value)


class Probe(Node):

    def __init__(self):
        super().__init__('composite_probe')
        self._cli = ActionClient(self, RunComposite, '/run_composite')
        self._exec = SingleThreadedExecutor()
        self._exec.add_node(self)

    def _spin_once(self, timeout=0.05):
        """Futures only resolve while the node spins."""
        self._exec.spin_once(timeout_sec=timeout)

    def run(self, args):
        if not self._cli.wait_for_server(timeout_sec=30.0):
            return {'status': 'NO_SERVER'}
        goal = RunComposite.Goal()
        goal.scenario_id = args.scenario
        goal.motion_profile_id = args.motion_profile
        goal.position_tolerance_m = args.tolerance
        goal.clearance_m = args.clearance
        # The chain must declare every object the fresh observation reports.
        for name, slot in zip(args.declare, args.slot):
            start = ObjectPosition()
            start.object_name = name
            start.position.x, start.position.y, start.position.z = slot
            goal.initial_objects.append(start)
        stage = CompositeStage()
        stage.stage_id = 'one'
        stage.object_name = args.object
        stage.place_pose.header.frame_id = 'world'
        stage.place_pose.pose.orientation.w = 1.
        p = stage.place_pose.pose.position
        p.x, p.y, p.z = args.place
        goal.stages = [stage]
        # Contract: these are positions that must be VACANT once the chain
        # finishes - the vacated start slots, not the destinations.
        for slot in args.vacate:
            empty = Point()
            empty.x, empty.y, empty.z = slot
            goal.final_empty_positions.append(empty)

        send = self._cli.send_goal_async(goal)
        t0 = time.monotonic()
        while not send.done():
            if time.monotonic() - t0 > 30.0:
                return {'status': 'SEND_TIMEOUT'}
            self._spin_once()
        handle = send.result()
        if handle is None or not handle.accepted:
            return {'status': 'REJECTED'}
        rf = handle.get_result_async()
        deadline = time.monotonic() + args.timeout
        while not rf.done():
            if time.monotonic() - deadline > 0:
                handle.cancel_goal_async()
                return {'status': 'RESULT_TIMEOUT'}
            self._spin_once()
        res = rf.result().result
        return {
            'status': 'RESULT',
            'outcome': name_of(RunComposite.Result, 'OUTCOME_', int(res.outcome)),
            'outcome_val': int(res.outcome),
            'error_code': name_of(RunComposite.Result, 'ERR_', int(res.error_code)),
            'error_code_val': int(res.error_code),
            'run_id': res.run_id,
            'completed_stage_ids': list(res.completed_stage_ids),
            'component_run_ids': list(res.component_run_ids),
            'evidence_id': res.evidence_id,
            'detail': res.detail,
            'wall_seconds': time.monotonic() - t0,
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--object', default='target_box_a')
    ap.add_argument('--declare', nargs='+',
                    default=['target_box_a', 'target_box_b'],
                    help='every object the world contains')
    ap.add_argument('--slot', nargs=3, type=float, action='append',
                    default=None, help='declared start position per --declare')
    ap.add_argument('--start', nargs=3, type=float, default=[0.22, 0.0, 0.0175])
    ap.add_argument('--place', nargs=3, type=float, default=[0.12, -0.15, 0.0175])
    ap.add_argument('--tolerance', type=float, default=0.06)
    ap.add_argument('--clearance', type=float, default=0.06)
    ap.add_argument('--motion-profile', default='demo_slow')
    ap.add_argument('--scenario', default='composite_probe_v1')
    ap.add_argument('--vacate', nargs=3, type=float, action='append',
                    default=None,
                    help='position that must be empty after the chain '
                         '(defaults to the start position)')
    ap.add_argument('--timeout', type=float, default=240.0)
    args = ap.parse_args()
    if not args.slot:
        args.slot = [[0.22, 0.0, 0.0175], [0.20, -0.18, 0.0175]]
    if not args.vacate:
        args.vacate = [args.start]
    rclpy.init()
    node = Probe()
    try:
        payload = node.run(args)
    finally:
        node.destroy_node()
        rclpy.shutdown()
    print('RESULT ' + json.dumps(payload, sort_keys=True))
    return 0 if payload.get('outcome_val') == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
