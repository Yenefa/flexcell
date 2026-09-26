#!/usr/bin/env python3
"""Experiment 3: can the ros2_control JointTrajectoryController be cancelled mid-motion?

Sends a multi-second trajectory DIRECTLY to /<controller>/follow_joint_trajectory
(bypassing move_group entirely), cancels partway, and measures what actually happened.

Usage: fjt_cancel_test.py <cancel_after_s> <trajectory_duration_s> [controller_ns]
"""
import sys
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter

from builtin_interfaces.msg import Duration
from control_msgs.action import FollowJointTrajectory
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

CANCEL_AFTER = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
DURATION = float(sys.argv[2]) if len(sys.argv) > 2 else 4.0
CTRL = sys.argv[3] if len(sys.argv) > 3 else '/arm_controller'
JOINTS = ['joint1', 'joint2', 'joint3', 'joint4']


def dur(s):
    d = Duration()
    d.sec = int(s)
    d.nanosec = int((s - int(s)) * 1e9)
    return d


class T(Node):
    def __init__(self):
        super().__init__('fjt_cancel_probe')
        self.set_parameters([Parameter('use_sim_time', value=True)])
        self.js = None
        self.create_subscription(JointState, '/joint_states', self._js, 50)
        self.cli = ActionClient(self, FollowJointTrajectory,
                                CTRL + '/follow_joint_trajectory')

    def _js(self, m):
        self.js = m

    def spin_for(self, s):
        end = time.time() + s
        while time.time() < end:
            rclpy.spin_once(self, timeout_sec=0.02)

    def pos(self):
        idx = {n: i for i, n in enumerate(self.js.name)}
        return [self.js.position[idx[j]] for j in JOINTS]

    def run(self):
        if not self.cli.wait_for_server(timeout_sec=10.0):
            print('RESULT action server %s/follow_joint_trajectory unavailable' % CTRL)
            return 2
        self.spin_for(2.0)
        start = self.pos()
        print('start joint pos:', ['%.4f' % v for v in start])

        # target: move joint1 by +0.8 rad, joint2 by +0.2, keep others
        end_pos = [start[0] + 0.8, start[1] + 0.2, start[2], start[3]]

        traj = JointTrajectory()
        traj.joint_names = list(JOINTS)
        n = 20
        for k in range(1, n + 1):
            f = k / float(n)
            pt = JointTrajectoryPoint()
            pt.positions = [start[i] + (end_pos[i] - start[i]) * f for i in range(4)]
            pt.velocities = [0.0] * 4
            pt.time_from_start = dur(DURATION * f)
            traj.points.append(pt)

        goal = FollowJointTrajectory.Goal()
        goal.trajectory = traj

        t0 = time.monotonic()
        sf = self.cli.send_goal_async(goal)
        while not sf.done():
            rclpy.spin_once(self, timeout_sec=0.02)
        gh = sf.result()
        print('goal accepted:', gh.accepted)
        if not gh.accepted:
            return 3

        rf = gh.get_result_async()
        cancelled = False
        pos_at_cancel = None
        t_cancel = None
        cancel_goals = None
        while not rf.done():
            rclpy.spin_once(self, timeout_sec=0.02)
            if not cancelled and time.monotonic() - t0 >= CANCEL_AFTER:
                pos_at_cancel = self.pos()
                t_cancel = time.monotonic()
                print('CANCEL at %.2fs, pos: %s' % (t_cancel - t0,
                      ['%.4f' % v for v in pos_at_cancel]))
                cf = gh.cancel_goal_async()
                while not cf.done():
                    rclpy.spin_once(self, timeout_sec=0.02)
                resp = cf.result()
                gc = getattr(resp, 'goals_canceling', None) or []
                cancel_goals = len(gc)
                print('cancel response: %s goals_canceling: %d'
                      % (type(resp).__name__, cancel_goals))
                cancelled = True

        res = rf.result().result
        code = int(res.error_code)  # control_msgs FollowJointTrajectory uses a plain int
        t_result = time.monotonic()
        print('controller result error_code:', code,
              '(SUCCESSFUL=0 INVALID_GOAL=-1 PATH_TOL=-4 GOAL_TOL=-5)')
        print('controller result error_string:', getattr(res, 'error_string', ''))
        self.spin_for(1.0)
        final = self.pos()
        print('final joint pos:', ['%.4f' % v for v in final])
        print('planned endpoint:', ['%.4f' % v for v in end_pos])
        dev = max(abs(final[i] - end_pos[i]) for i in range(4))
        print('max deviation from planned endpoint (rad): %.5f' % dev)
        print('reached original endpoint:', dev < 0.02)
        if t_cancel is not None:
            print('stop latency (cancel -> result): %.3f s' % (t_result - t_cancel))
        print('wall total: %.3f s' % (t_result - t0))
        return 0


def main():
    rclpy.init()
    n = T()
    try:
        rc = n.run()
    finally:
        n.destroy_node()
        rclpy.shutdown()
    sys.exit(rc)


main()
