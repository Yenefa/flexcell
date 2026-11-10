#!/usr/bin/env python3
"""EvoBot composite task client.

WHY: the existing w1_client can only fire the fixed demo/task flows, so there is no
way to hand the robot an arbitrary task-derived stage list. RunComposite already
exists on the server and accepts an explicit bounded plan; this is its missing
client. It dispatches a plan and prints the terminal result as JSON, so the
observation bridge and the independent evaluator can grade it afterwards.

It does not plan, retry, or interpret. Planning is the caller's job; judging is the
evaluator's job. Keeping this dumb is what makes Baseline A a fair baseline.
"""
import argparse
import json
import sys

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from flexcell_interfaces.action import RunComposite
from flexcell_interfaces.msg import CompositeStage, ObjectPosition
from geometry_msgs.msg import Point


class CompositeClient(Node):
    def __init__(self):
        super().__init__("evobot_composite_client")
        self._client = ActionClient(self, RunComposite, "run_composite")

    def run(self, plan, timeout_s):
        if not self._client.wait_for_server(timeout_sec=30.0):
            return {"ok": False, "error": "run_composite action server unavailable"}
        goal = RunComposite.Goal()
        goal.scenario_id = str(plan.get("task_id", "evobot-task"))
        goal.initial_objects = [
            ObjectPosition(object_name=o["object_name"],
                           position=Point(x=float(o["position"][0]),
                                          y=float(o["position"][1]),
                                          z=float(o["position"][2])))
            for o in plan.get("initial_objects", [])]
        goal.stages = [
            CompositeStage(stage_id=s["stage_id"], object_name=s["object_name"],
                           place_pose=_pose(s["place_pose"]))
            for s in plan["stages"]]
        goal.final_empty_positions = [Point(x=float(p[0]), y=float(p[1]), z=float(p[2]))
                                     for p in plan.get("final_empty_positions", [])]
        goal.position_tolerance_m = float(plan.get("position_tolerance_m", 0.02))
        goal.clearance_m = float(plan.get("clearance_m", 0.06))
        goal.motion_profile_id = str(plan.get("motion_profile_id", "demo_slow"))
        goal.pause_after_stages = int(plan.get("pause_after_stages", 0))
        goal.resume_run_id = ""
        goal.resume_receipt_sha256 = ""

        send = self._client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, send, timeout_sec=timeout_s)
        handle = send.result()
        if handle is None or not handle.accepted:
            return {"ok": False, "error": "goal rejected"}
        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future, timeout_sec=timeout_s)
        wrapped = result_future.result()
        if wrapped is None:
            return {"ok": False, "error": "no terminal result within %.0fs" % timeout_s}
        r = wrapped.result
        return {
            "ok": True,
            "outcome": int(r.outcome),
            "error_code": int(r.error_code),
            "run_id": r.run_id,
            "completed_stage_ids": list(r.completed_stage_ids),
            "detail": r.detail,
            "evidence_id": r.evidence_id,
        }


def _pose(xyz):
    from geometry_msgs.msg import PoseStamped
    ps = PoseStamped()
    ps.header.frame_id = "world"
    ps.pose.position.x = float(xyz[0])
    ps.pose.position.y = float(xyz[1])
    ps.pose.position.z = float(xyz[2])
    ps.pose.orientation.w = 1.0
    return ps


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True, help="JSON file with stages and initial_objects")
    ap.add_argument("--timeout", type=float, default=300.0)
    args = ap.parse_args(argv)
    with open(args.plan, encoding="utf-8") as f:
        plan = json.load(f)
    rclpy.init()
    node = CompositeClient()
    try:
        result = node.run(plan, args.timeout)
    finally:
        node.destroy_node()
        rclpy.shutdown()
    print("RESULT " + json.dumps(result))
    return 0 if result.get("ok") and result.get("outcome") == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
