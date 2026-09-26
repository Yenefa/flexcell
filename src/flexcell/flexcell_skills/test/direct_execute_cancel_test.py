#!/usr/bin/env python3
"""Isolate: does /execute_trajectory honour a cancel at all?

Plan via /plan_kinematic_path, send to /execute_trajectory, cancel after N seconds,
then report the action result code AND the achieved joint state vs the planned end.
"""
import sys
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter

from geometry_msgs.msg import Pose, Vector3
from moveit_msgs.action import ExecuteTrajectory
from moveit_msgs.msg import (BoundingVolume, Constraints, MotionPlanRequest,
                             MoveItErrorCodes, PositionConstraint, WorkspaceParameters)
from moveit_msgs.srv import GetMotionPlan
from sensor_msgs.msg import JointState
from shape_msgs.msg import SolidPrimitive

CANCEL_AFTER = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
TARGET = (0.135275, 0.082566, 0.097307)


class T(Node):
    def __init__(self):
        super().__init__('direct_exec_cancel')
        self.set_parameters([Parameter('use_sim_time', value=True)])
        self.js = None
        self.create_subscription(JointState, '/joint_states', self._js, 50)
        self.plan = self.create_client(GetMotionPlan, '/plan_kinematic_path')
        self.exec_cli = ActionClient(self, ExecuteTrajectory, '/execute_trajectory')

    def _js(self, m):
        self.js = m

    def spin_for(self, s):
        end = time.time() + s
        while time.time() < end:
            rclpy.spin_once(self, timeout_sec=0.05)

    def run(self):
        self.plan.wait_for_service(timeout_sec=5.0)
        self.exec_cli.wait_for_server(timeout_sec=5.0)
        self.spin_for(2.0)

        req = MotionPlanRequest()
        req.group_name = 'arm'
        req.num_planning_attempts = 10
        req.allowed_planning_time = 5.0
        req.max_velocity_scaling_factor = 0.05
        req.max_acceleration_scaling_factor = 0.05
        ws = WorkspaceParameters()
        ws.header.frame_id = 'world'
        ws.min_corner.x, ws.min_corner.y, ws.min_corner.z = -0.45, -0.45, -0.15
        ws.max_corner.x, ws.max_corner.y, ws.max_corner.z = 0.45, 0.45, 0.75
        req.workspace_parameters = ws
        c = Constraints()
        pc = PositionConstraint()
        pc.header.frame_id = 'world'
        pc.header.stamp = self.get_clock().now().to_msg()
        pc.link_name = 'end_effector_link'
        pc.target_point_offset = Vector3(x=0.0, y=0.0, z=0.0)
        bv = BoundingVolume()
        sp = SolidPrimitive()
        sp.type = SolidPrimitive.SPHERE
        sp.dimensions = [0.02]
        bv.primitives.append(sp)
        p = Pose()
        p.position.x, p.position.y, p.position.z = TARGET
        p.orientation.w = 1.0
        bv.primitive_poses.append(p)
        pc.constraint_region = bv
        pc.weight = 1.0
        c.position_constraints.append(pc)
        req.goal_constraints.append(c)

        sr = GetMotionPlan.Request()
        sr.motion_plan_request = req
        f = self.plan.call_async(sr)
        while not f.done():
            rclpy.spin_once(self, timeout_sec=0.05)
        mpr = f.result().motion_plan_response
        print('planning code:', mpr.error_code.val)
        traj = mpr.trajectory
        names = list(traj.joint_trajectory.joint_names)
        planned_end = list(traj.joint_trajectory.points[-1].positions)
        dur = traj.joint_trajectory.points[-1].time_from_start
        print('planned waypoints:', len(traj.joint_trajectory.points),
              'duration_s: %.3f' % (dur.sec + dur.nanosec * 1e-9))

        g = ExecuteTrajectory.Goal()
        g.trajectory = traj
        t0 = time.monotonic()
        sf = self.exec_cli.send_goal_async(g)
        while not sf.done():
            rclpy.spin_once(self, timeout_sec=0.05)
        gh = sf.result()
        print('execute goal accepted:', gh.accepted)

        rf = gh.get_result_async()
        cancelled = False
        while not rf.done():
            rclpy.spin_once(self, timeout_sec=0.05)
            if not cancelled and time.monotonic() - t0 >= CANCEL_AFTER:
                print('CANCEL at %.2fs' % (time.monotonic() - t0))
                cf = gh.cancel_goal_async()
                while not cf.done():
                    rclpy.spin_once(self, timeout_sec=0.05)
                resp = cf.result()
                gc = getattr(resp, 'goals_canceling', None) or []
                print('cancel response type:', type(resp).__name__,
                      'goals_canceling:', len(gc))
                cancelled = True

        code = int(rf.result().result.error_code.val)
        print('execute result code:', code,
              '(PREEMPTED=-7 SUCCESS=1 TIMED_OUT=-6)')
        self.spin_for(1.0)
        idx = {n: i for i, n in enumerate(self.js.name)}
        devs = [abs(self.js.position[idx[n]] - t)
                for n, t in zip(names, planned_end) if n in idx]
        print('max deviation from planned end (rad): %.5f' % max(devs))
        print('wall_s: %.3f' % (time.monotonic() - t0))
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
