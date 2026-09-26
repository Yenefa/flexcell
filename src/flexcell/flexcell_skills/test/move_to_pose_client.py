#!/usr/bin/env python3
"""Smoke-test client for the FlexCell MoveToPose action.

Usage:
  move_to_pose_client.py --pose X Y Z QX QY QZ QW [--frame world]
                         [--profile demo_slow] [--deadline 20000]
                         [--cancel-after SEC] [--timeout SEC]
"""
import argparse
import json
import sys
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter

from geometry_msgs.msg import PoseStamped
from flexcell_interfaces.action import MoveToPose

PHASE = {
    MoveToPose.Feedback.PHASE_VALIDATING: 'VALIDATING',
    MoveToPose.Feedback.PHASE_PLANNING: 'PLANNING',
    MoveToPose.Feedback.PHASE_EXECUTING: 'EXECUTING',
    MoveToPose.Feedback.PHASE_CHECKING: 'CHECKING',
    MoveToPose.Feedback.PHASE_STOPPING: 'STOPPING',
}


def const_name(cls, prefix, value):
    for k, v in vars(cls).items():
        if k.startswith(prefix) and isinstance(v, int) and v == value:
            return k
    return str(value)


class Client(Node):

    def __init__(self):
        super().__init__('move_to_pose_client')
        self.set_parameters([Parameter('use_sim_time', value=True)])
        self.cli = ActionClient(self, MoveToPose, '/move_to_pose')
        self.phases = []
        self.gh = None
        self.executing_t0 = None

    def fb(self, msg):
        p = msg.feedback.phase
        name = PHASE.get(p, str(p))
        if not self.phases or self.phases[-1] != name:
            self.phases.append(name)
            print('FEEDBACK %-10s elapsed_ms=%d' % (name, msg.feedback.elapsed_ms), flush=True)
        if p == MoveToPose.Feedback.PHASE_EXECUTING and self.executing_t0 is None:
            self.executing_t0 = time.monotonic()

    def run(self, args):
        if not self.cli.wait_for_server(timeout_sec=10.0):
            print('RESULT ' + json.dumps({'client_error': 'action server unavailable'}))
            return 2

        goal = MoveToPose.Goal()
        goal.request_id = args.request_id
        goal.target = PoseStamped()
        goal.target.header.frame_id = args.frame
        goal.target.header.stamp = self.get_clock().now().to_msg()
        goal.target.pose.position.x = args.pose[0]
        goal.target.pose.position.y = args.pose[1]
        goal.target.pose.position.z = args.pose[2]
        goal.target.pose.orientation.x = args.pose[3]
        goal.target.pose.orientation.y = args.pose[4]
        goal.target.pose.orientation.z = args.pose[5]
        goal.target.pose.orientation.w = args.pose[6]
        goal.motion_profile_id = args.profile
        goal.expected_world_revision = args.expected_revision
        goal.deadline_ms = args.deadline

        print('SENDING request_id=%s frame=%s pose=%s profile=%s deadline=%d'
              % (goal.request_id or '<auto>', args.frame,
                 ['%.4f' % v for v in args.pose], args.profile, args.deadline), flush=True)

        t0 = time.monotonic()
        send_fut = self.cli.send_goal_async(goal, feedback_callback=self.fb)
        while not send_fut.done():
            rclpy.spin_once(self, timeout_sec=0.05)
        self.gh = send_fut.result()
        if self.gh is None or not self.gh.accepted:
            print('RESULT ' + json.dumps({'client_error': 'goal rejected'}))
            return 3

        res_fut = self.gh.get_result_async()
        cancel_sent = False
        while not res_fut.done():
            rclpy.spin_once(self, timeout_sec=0.05)
            if not cancel_sent and args.cancel_after and time.monotonic() - t0 >= args.cancel_after:
                print('CANCEL_REQUESTED after %.2fs (wall)' % args.cancel_after, flush=True)
                self.gh.cancel_goal_async()
                cancel_sent = True
            if (not cancel_sent and args.cancel_after_executing
                    and self.executing_t0 is not None
                    and time.monotonic() - self.executing_t0 >= args.cancel_after_executing):
                print('CANCEL_REQUESTED %.2fs into EXECUTING' % args.cancel_after_executing,
                      flush=True)
                self.gh.cancel_goal_async()
                cancel_sent = True
            if time.monotonic() - t0 > args.timeout:
                print('CLIENT_TIMEOUT after %.1fs' % args.timeout)
                break

        if not res_fut.done():
            return 4

        r = res_fut.result().result
        out = {
            'outcome': const_name(MoveToPose.Result, 'OUTCOME_', r.outcome),
            'outcome_val': int(r.outcome),
            'error_code': const_name(MoveToPose.Result, 'ERR_', r.error_code),
            'error_code_val': int(r.error_code),
            'moveit_error_code': int(r.moveit_error_code),
            'has_reached_pose': bool(r.has_reached_pose),
            'position_error_m': r.position_error_m,
            'orientation_error_rad': r.orientation_error_rad,
            'orientation_enforced': bool(r.orientation_enforced),
            'execution_started': bool(r.execution_started),
            'world_revision_before': int(r.world_revision_before),
            'world_revision_after': int(r.world_revision_after),
            'evidence_id': r.evidence_id,
            'detail': r.detail,
            'phases': self.phases,
            'wall_seconds': round(time.monotonic() - t0, 3),
        }
        if r.has_reached_pose:
            out['reached_pose'] = {
                'frame_id': r.reached_pose.header.frame_id,
                'position': [r.reached_pose.pose.position.x,
                             r.reached_pose.pose.position.y,
                             r.reached_pose.pose.position.z],
            }
        print('RESULT ' + json.dumps(out, indent=2), flush=True)
        return 0 if r.outcome == MoveToPose.Result.OUTCOME_SUCCEEDED else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pose', nargs=7, type=float, required=True,
                    metavar=('X', 'Y', 'Z', 'QX', 'QY', 'QZ', 'QW'))
    ap.add_argument('--frame', default='world')
    ap.add_argument('--profile', default='demo_slow')
    ap.add_argument('--deadline', type=int, default=20000)
    ap.add_argument('--request-id', default='')
    ap.add_argument('--expected-revision', type=int, default=0)
    ap.add_argument('--cancel-after', type=float, default=0.0)
    ap.add_argument('--cancel-after-executing', type=float, default=0.0)
    ap.add_argument('--timeout', type=float, default=90.0)
    args = ap.parse_args()

    rclpy.init()
    c = Client()
    try:
        rc = c.run(args)
    finally:
        c.destroy_node()
        rclpy.shutdown()
    sys.exit(rc)


if __name__ == '__main__':
    main()
