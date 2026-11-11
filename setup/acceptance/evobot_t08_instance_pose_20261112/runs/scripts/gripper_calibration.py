#!/usr/bin/env python3
"""G1 / G3 gripper-aperture calibration.

WHAT QUESTION THIS ANSWERS AND WHY IT CANNOT BE ANSWERED FROM THE PUSH RUNS
    verify.py's gripper gate bounds the TOTAL VARIATION of the gripper aperture
    during the trial window (limit 0.002, joint units). It exists to separate
    "the gripper closed on the object = a grasp/carry" from "the fingers stayed
    where they were = a push".

    Measured G2 (the push runs) aperture travel spans 0.000013 to 0.004824 in
    these units, and the gate rejects at 0.002. Two of those push trials sit
    above the limit and two below, so the gate is deciding real verdicts on a
    measurement whose signal and noise have never been separated.

    The separation needs two calibrations that the push runs cannot provide:
      G1  a GENUINE GRASP of the 35 mm block. The fingers are commanded to
          close on it and stall. How far does the aperture actually move, and
          how stable is it once holding?
      G3  a CLOSED-FINGER SWEEP with no object present. Fingers commanded shut,
          then the arm sweeps the same kind of trajectory a push uses. Any
          aperture movement here is pure noise: nothing to grasp, nothing to
          touch.

    If G1 separates from G2 by more than G3's noise floor, a threshold exists in
    the gap. If it does not, then no number fixes the gate and it needs a
    different observable. This script MEASURES; it does not decide and it does
    not change any limit.

WHAT IT RECORDS
    /joint_states over the whole operation, plus monotonic timestamps of each
    phase boundary, so the analysis can window the span three ways:
      full_window  - the analogue of what the gate computes over a trial
      close_window - the commanded close itself (G1 only)
      hold_window  - after the close, while the object is held / while sweeping
"""
import json
import sys
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from control_msgs.action import GripperCommand
from sensor_msgs.msg import JointState


def main(argv):
    mode = argv[1]              # "G1" or "G3"
    outdir = argv[2]
    spec_path = argv[3]
    gripper_joint = "gripper_left_joint"
    open_position = 0.02
    close_position = -0.011
    max_effort = 10.0

    spec = json.load(open(spec_path, encoding="utf-8"))
    target = spec["objects"][0]["name"]
    box = spec["objects"][0]["initial_pose"]

    rclpy.init()
    node = Node("t08_gripper_calibration")
    marks = {}
    samples = []

    def box_pose():
        """Ground-truth pose of the target, so a 'grasp' is proven, not assumed."""
        try:
            from flexcell_skills.common import sample_gz_pose
            pose, err = sample_gz_pose(target, timeout_s=8.0)
            if pose is None:
                return {"error": str(err)}
            return [round(float(v), 6) for v in pose[0]]
        except Exception as exc:                                # noqa: BLE001
            return {"error": str(exc)}

    def on_joint(msg):
        names = list(msg.name)
        if gripper_joint not in names:
            return
        index = names.index(gripper_joint)
        if index >= len(msg.position):
            return
        samples.append([time.monotonic_ns(), float(msg.position[index])])

    node.create_subscription(JointState, "/joint_states", on_joint, 50)

    from flexcell_interfaces.action import MoveToPose
    move_client = ActionClient(node, MoveToPose, "/move_to_pose")
    grip_client = ActionClient(node, GripperCommand, "/gripper_controller/gripper_cmd")

    def spin_for(seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=0.05)

    def move_to(xyz, label, timeout_s=90.0):
        from geometry_msgs.msg import PoseStamped
        from builtin_interfaces.msg import Time as TimeMsg
        goal = MoveToPose.Goal()
        goal.target = PoseStamped()
        goal.target.header.frame_id = "world"
        goal.target.header.stamp = TimeMsg()
        goal.target.pose.position.x = float(xyz[0])
        goal.target.pose.position.y = float(xyz[1])
        goal.target.pose.position.z = float(xyz[2])
        goal.target.pose.orientation.w = 1.0
        goal.motion_profile_id = "demo_slow"
        goal.deadline_ms = int(timeout_s * 1000)
        goal.request_id = "calib-" + label
        goal.expected_world_revision = 0
        if not move_client.wait_for_server(timeout_sec=15.0):
            return {"ok": False, "error": "move_to_pose unavailable"}
        future = move_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(node, future, timeout_sec=15.0)
        handle = future.result()
        if handle is None or not handle.accepted:
            return {"ok": False, "error": "goal rejected"}
        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(node, result_future, timeout_sec=timeout_s)
        wrapped = result_future.result()
        if wrapped is None:
            return {"ok": False, "error": "no result"}
        r = wrapped.result
        return {"ok": int(r.outcome) == 0, "outcome": int(r.outcome),
                "error_code": int(r.error_code), "detail": str(r.detail)[:200]}

    def gripper_command(position, label, timeout_s=30.0):
        goal = GripperCommand.Goal()
        goal.command.position = float(position)
        goal.command.max_effort = float(max_effort)
        if not grip_client.wait_for_server(timeout_sec=15.0):
            return {"ok": False, "error": "gripper action unavailable"}
        future = grip_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(node, future, timeout_sec=15.0)
        handle = future.result()
        if handle is None or not handle.accepted:
            return {"ok": False, "error": "gripper goal rejected"}
        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(node, result_future, timeout_sec=timeout_s)
        wrapped = result_future.result()
        if wrapped is None:
            return {"ok": False, "error": "gripper result missing"}
        r = wrapped.result
        return {"ok": True, "reached_goal": bool(r.reached_goal),
                "stalled": bool(r.stalled), "position": float(r.position),
                "effort": float(r.effort), "requested": float(position)}

    report = {"mode": mode, "gripper_joint": gripper_joint,
              "limits": {"open_position": open_position,
                         "close_position": close_position,
                         "max_effort": max_effort},
              "task_spec": spec_path, "target_object": target,
              "box_initial_pose": box, "phases": {}, "errors": []}

    # warm-up: let /joint_states flow before any phase marker
    spin_for(3.0)

    if mode == "G1":
        # ---- G1: genuine grasp of the 35 mm block -------------------------
        # MEASURED CORRECTION TO THE OBVIOUS CHOICE.
        # The first G1 attempt reused pick_server's own declared grasp target
        # (box_z + grasp_dz_m = box_z + 0.16). That is NOT where the fingers
        # reach the block: run 1 recorded zero gripper contact with the target,
        # the aperture closed fully to -0.011 without stalling, and the box
        # never rose. The reason is in the archived picks: attach_gap_m is
        # ~0.166 m, i.e. that stack "grasps" by MAGNETIC CARRY from 166 mm away,
        # not by fingers. So the grasp target here is derived from the block's
        # own geometry instead: fingers level with the block centre, close on
        # the 35 mm faces. Hover stays high for a clean approach.
        hover = [box[0], box[1], box[2] + 0.22]
        grasp = [box[0], box[1], box[2] + 0.000]
        marks["t_start"] = time.monotonic_ns()
        report["box_before"] = box_pose()
        report["phases"]["open"] = gripper_command(open_position, "open")
        report["phases"]["hover"] = move_to(hover, "hover")
        report["phases"]["descend"] = move_to(grasp, "grasp")
        marks["t_close_start"] = time.monotonic_ns()
        report["phases"]["close"] = gripper_command(close_position, "close")
        marks["t_close_end"] = time.monotonic_ns()
        report["grasp_evidence"] = {
            "close_result": report["phases"]["close"],
            "requested_close": close_position,
            "full_stroke": abs(open_position - close_position),
        }
        spin_for(3.0)                 # hold while "holding" the block
        marks["t_hold_end"] = time.monotonic_ns()
        # lift slightly to prove the grasp holds; aperture should not change
        report["phases"]["lift"] = move_to([grasp[0], grasp[1], grasp[2] + 0.10], "lift")
        spin_for(1.0)
        report["box_after_lift"] = box_pose()
        report["grasp_evidence"]["box_rose_m"] = (
            None if not isinstance(report.get("box_before"), list)
            or not isinstance(report.get("box_after_lift"), list)
            else round(report["box_after_lift"][2] - report["box_before"][2], 6))
        marks["t_end"] = time.monotonic_ns()
        report["phases"]["release"] = gripper_command(open_position, "release")

    elif mode == "G3":
        # ---- G3: closed-finger sweep with NO object present ---------------
        # Sweep at y = +0.16 so that neither box is near: the nearest, box A,
        # sits at y = +0.03, i.e. 130 mm away, and the fingers are ~30 mm wide.
        # The contact log is checked afterwards to confirm nothing was touched.
        sweep_y = 0.16
        sweep_z = 0.0200
        report["sweep_geometry"] = {"y": sweep_y, "z": sweep_z,
                                    "from_x": 0.24, "to_x": 0.12}
        marks["t_start"] = time.monotonic_ns()
        report["phases"]["open"] = gripper_command(open_position, "open")
        report["phases"]["close"] = gripper_command(close_position, "close")
        marks["t_close_end"] = time.monotonic_ns()
        report["phases"]["sweep_start"] = move_to([0.24, sweep_y, sweep_z], "sweep_start")
        marks["t_sweep_start"] = time.monotonic_ns()
        report["phases"]["sweep_end"] = move_to([0.12, sweep_y, sweep_z], "sweep_end")
        marks["t_sweep_end"] = time.monotonic_ns()
        spin_for(1.0)
        marks["t_end"] = time.monotonic_ns()
    else:
        raise SystemExit("mode must be G1 or G3")

    report["phase_marks_monotonic_ns"] = marks
    report["joint_samples"] = samples
    with open(outdir + "/gripper_calibration.json", "w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != "joint_samples"},
                     indent=2)[:3000])
    print("SAMPLES", len(samples))
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
