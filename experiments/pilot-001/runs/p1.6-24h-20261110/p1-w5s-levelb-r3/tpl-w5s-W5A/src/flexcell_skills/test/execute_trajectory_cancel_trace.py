#!/usr/bin/env python3
"""Where does the cancel get lost?

Plans a trajectory, sends it to /execute_trajectory (move_group), cancels partway,
and traces BOTH action status topics to see whether the cancel ever reaches the
controller:

    /execute_trajectory/_action/status                     (move_group goal)
    /arm_controller/follow_joint_trajectory/_action/status (controller goal)
"""
import sys
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter

from action_msgs.msg import GoalStatusArray
from geometry_msgs.msg import Pose, Vector3
from moveit_msgs.action import ExecuteTrajectory
from moveit_msgs.msg import (BoundingVolume, Constraints, MotionPlanRequest,
                             MoveItErrorCodes, PositionConstraint, WorkspaceParameters)
from moveit_msgs.srv import GetMotionPlan
from sensor_msgs.msg import JointState
from shape_msgs.msg import SolidPrimitive

CANCEL_AFTER = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
TARGET = (0.135275, 0.082566, 0.097307)

STATUS = {0: 'UNKNOWN', 1: 'ACCEPTED', 2: 'EXECUTING', 3: 'CANCELING',
          4: 'SUCCEEDED', 5: 'CANCELED', 6: 'ABORTED'}


class T(Node):
    def __init__(self):
        super().__init__('exec_cancel_trace')
        self.set_parameters([Parameter('use_sim_time', value=True)])
        self.js = None
        self.t0 = time.monotonic()
        self.seen = {}
        self.create_subscription(JointState, '/joint_states', self._js, 50)
        self.create_subscription(GoalStatusArray, '/execute_trajectory/_action/status',
                                 lambda m: self._status('EXEC_TRJ', m), 50)
        self.create_subscription(
            GoalStatusArray, '/arm_controller/follow_joint_trajectory/_action/status',
            lambda m: self._status('FJT', m), 50)
        self.plan = self.create_client(GetMotionPlan, '/plan_kinematic_path')
        self.exec_cli = ActionClient(self, ExecuteTrajectory, '/execute_trajectory')

    def _js(self, m):
        self.js = m

    def _status(self, tag, msg):
        for st in msg.status_list:
            key = (tag, bytes(st.goal_info.goal_id.uuid).hex()[:8])
            name = STATUS.get(st.status, str(st.status))
            if self.seen.get(key) != name:
                self.seen[key] = name
                print('  [%6.2fs] %-9s goal=%s -> %s'
                      % (time.monotonic() - self.t0, tag, key[1], name), flush=True)

    def spin_for(self, s):
        end = time.time() + s
        while time.time() < end:
            rclpy.spin_once(self, timeout_sec=0.02)

    def run(self):
        self.plan.wait_for_service(timeout_sec=5.0)
        self.exec_cli.wait_for_server(timeout_sec=5.0)
        self.spin_for(1.5)

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
        sp.dimensions = [0.008]
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
            rclpy.spin_once(self, timeout_sec=0.02)
        mpr = f.result().motion_plan_response
        traj = mpr.trajectory
        names = list(traj.joint_trajectory.joint_names)
        planned_end = list(traj.joint_trajectory.points[-1].positions)
        d = traj.joint_trajectory.points[-1].time_from_start
        print('planning code: %d  waypoints: %d  duration: %.3fs'
              % (mpr.error_code.val, len(traj.joint_trajectory.points),
                 d.sec + d.nanosec * 1e-9))

        g = ExecuteTrajectory.Goal()
        g.trajectory = traj
        self.t0 = time.monotonic()
        sf = self.exec_cli.send_goal_async(g)
        while not sf.done():
            rclpy.spin_once(self, timeout_sec=0.02)
        gh = sf.result()
        print('execute goal accepted:', gh.accepted)
        print('status trace:')

        rf = gh.get_result_async()
        cancelled = False
        while not rf.done():
            rclpy.spin_once(self, timeout_sec=0.02)
            if not cancelled and time.monotonic() - self.t0 >= CANCEL_AFTER:
                print('CANCEL sent at %.2fs' % (time.monotonic() - self.t0))
                cf = gh.cancel_goal_async()
                while not cf.done():
                    rclpy.spin_once(self, timeout_sec=0.02)
                gc = getattr(cf.result(), 'goals_canceling', None) or []
                print('execute_trajectory cancel response: goals_canceling=%d' % len(gc))
                cancelled = True

        code = int(rf.result().result.error_code.val)
        print('execute_trajectory result code: %d' % code)
        self.spin_for(1.5)
        idx = {n: i for i, n in enumerate(self.js.name)}
        devs = [abs(self.js.position[idx[n]] - t)
                for n, t in zip(names, planned_end) if n in idx]
        dev = max(devs)
        print('max deviation from planned endpoint: %.5f rad' % dev)
        print('reached original endpoint:', dev < 0.02)
        print('wall total: %.3f s' % (time.monotonic() - self.t0))
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
