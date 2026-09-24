#!/usr/bin/env python3
"""OpenMANIPULATOR-X MoveIt 2 Plan & Execute via the native move_group action interface.

Plan  : MoveGroup action (/move_action) with plan_only=True
Execute: ExecuteTrajectory action (/execute_trajectory) with the returned trajectory
"""
import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from sensor_msgs.msg import JointState
from moveit_msgs.action import MoveGroup, ExecuteTrajectory
from moveit_msgs.msg import (
    MotionPlanRequest, Constraints, JointConstraint, PlanningOptions,
    RobotState, MoveItErrorCodes,
)

GROUP_NAME = "arm"
JOINTS = ["joint1", "joint2", "joint3", "joint4"]
# Target joint values: [joint1, joint2, joint3, joint4] (default: demo pose)
TARGET = [float(v) for v in sys.argv[1:5]] if len(sys.argv) >= 5 else [0.6, -0.9, 0.9, 0.5]


class PlanExecute(Node):
    def __init__(self):
        super().__init__("omx_plan_execute")
        self.js = None
        self.create_subscription(JointState, "/joint_states", self.on_js, 10)
        self.mg = ActionClient(self, MoveGroup, "/move_action")
        self.et = ActionClient(self, ExecuteTrajectory, "/execute_trajectory")

    def on_js(self, msg):
        self.js = msg

    def snapshot(self):
        if self.js is None:
            return {}
        return dict(zip(self.js.name, self.js.position))

    def spin_for(self, seconds):
        end = time.time() + seconds
        while time.time() < end:
            rclpy.spin_once(self, timeout_sec=0.05)

    def build_request(self):
        req = MotionPlanRequest()
        req.group_name = GROUP_NAME
        req.num_planning_attempts = 10
        req.allowed_planning_time = 5.0
        req.max_velocity_scaling_factor = 0.5
        req.max_acceleration_scaling_factor = 0.5
        req.start_state = RobotState()
        c = Constraints()
        for name, pos in zip(JOINTS, TARGET):
            jc = JointConstraint()
            jc.joint_name = name
            jc.position = float(pos)
            jc.tolerance_above = 0.01
            jc.tolerance_below = 0.01
            jc.weight = 1.0
            c.joint_constraints.append(jc)
        req.goal_constraints.append(c)
        return req

    def run(self):
        print("waiting for /move_action and /execute_trajectory ...", flush=True)
        self.mg.wait_for_server()
        self.et.wait_for_server()
        self.spin_for(2.0)

        before = self.snapshot()
        print("BEFORE /joint_states:", {k: round(v, 4) for k, v in before.items() if k in JOINTS}, flush=True)

        # ---------------- PLAN ----------------
        goal = MoveGroup.Goal()
        goal.request = self.build_request()
        goal.planning_options = PlanningOptions()
        goal.planning_options.plan_only = True
        goal.planning_options.look_around = False
        goal.planning_options.replan = False

        fut = self.mg.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, fut)
        gh = fut.result()
        if gh is None or not gh.accepted:
            print("PLAN_FAILED: goal rejected", flush=True)
            return 2
        rf = gh.get_result_async()
        rclpy.spin_until_future_complete(self, rf)
        res = rf.result().result

        print("PLAN error_code =", res.error_code.val,
              " planning_time =", round(res.planning_time, 4), flush=True)
        if res.error_code.val != MoveItErrorCodes.SUCCESS:
            print("PLAN_FAILED", flush=True)
            return 3

        traj = res.planned_trajectory
        jt = traj.joint_trajectory
        print("PLANNED joints:", list(jt.joint_names), flush=True)
        print("PLANNED waypoints:", len(jt.points), flush=True)
        print("PLANNED final positions:", [round(x, 4) for x in jt.points[-1].positions], flush=True)
        print("PLANNED duration: %.3f s" % (jt.points[-1].time_from_start.sec +
                                            jt.points[-1].time_from_start.nanosec * 1e-9), flush=True)

        # ---------------- EXECUTE ----------------
        egoal = ExecuteTrajectory.Goal()
        egoal.trajectory = traj
        efut = self.et.send_goal_async(egoal)
        rclpy.spin_until_future_complete(self, efut)
        egh = efut.result()
        if egh is None or not egh.accepted:
            print("EXECUTE_FAILED: goal rejected", flush=True)
            return 4
        erf = egh.get_result_async()
        rclpy.spin_until_future_complete(self, erf)
        eres = erf.result().result
        print("EXECUTE error_code =", eres.error_code.val, flush=True)
        if eres.error_code.val != MoveItErrorCodes.SUCCESS:
            print("EXECUTE_FAILED", flush=True)
            return 5

        self.spin_for(3.0)
        after = self.snapshot()
        print("AFTER  /joint_states:", {k: round(v, 4) for k, v in after.items() if k in JOINTS}, flush=True)

        moved = {k: round(after.get(k, 0.0) - before.get(k, 0.0), 4) for k in JOINTS}
        print("DELTA  /joint_states:", moved, flush=True)
        ok = all(abs(moved[k]) > 0.05 for k in JOINTS)
        print("MOTION_DETECTED =", ok, flush=True)
        return 0 if ok else 6


def main():
    rclpy.init()
    node = PlanExecute()
    try:
        rc = node.run()
    except Exception as exc:  # noqa: BLE001
        print("EXCEPTION:", repr(exc), flush=True)
        rc = 9
    finally:
        node.destroy_node()
        rclpy.shutdown()
    print("RC =", rc, flush=True)
    sys.exit(rc)


if __name__ == "__main__":
    main()
