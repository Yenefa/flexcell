"""Execute a frozen Baseline B plan through the real RunComposite executor.

Why this is a module and not a heredoc inside the batch shell script: the executor
logic was wrong three times in a row (empty initial_objects, guessed field names,
wrong message type) and each mistake only surfaced after a simulator start. As a
module it can be imported and asserted offline, so interface errors cost a second
instead of a simulation cycle.

The plan comes from the recorded Baseline B artefacts and is already in the executor
vocabulary: task_id, initial_objects, stages[].place_pose as a 3-vector, and its own
motion_profile_id. Those values are used as recorded; this module does not re-plan.
"""
import argparse
import json
import sys


def load_plan(path):
    with open(path, encoding="utf-8") as f:
        plan = json.load(f)
    missing = [k for k in ("task_id", "initial_objects", "stages") if k not in plan]
    if missing:
        raise SystemExit("plan is missing required keys: %s" % missing)
    return plan


def build_goal(plan, run_composite, composite_stage, object_position, point,
               pose_stamped):
    """Build a RunComposite.Goal from the recorded plan.

    Every field name here is asserted by benchmark/tools/check_ros_interfaces.py, so a
    renamed field fails offline rather than mid-run.
    """
    goal = run_composite.Goal()
    goal.scenario_id = plan["task_id"]
    goal.motion_profile_id = plan.get("motion_profile_id") or "legacy"
    goal.position_tolerance_m = float(plan.get("position_tolerance_m", 0.02))
    goal.clearance_m = float(plan.get("clearance_m", 0.05))
    goal.pause_after_stages = 0
    goal.resume_run_id = ""
    goal.resume_receipt_sha256 = ""
    goal.initial_objects = []
    for entry in plan["initial_objects"]:
        op = object_position()
        op.object_name = entry["object_name"]
        pos = entry["position"]
        op.position = point(x=float(pos[0]), y=float(pos[1]), z=float(pos[2]))
        goal.initial_objects.append(op)
    goal.stages = []
    for entry in plan["stages"]:
        st = composite_stage()
        st.stage_id = entry["stage_id"]
        st.object_name = entry["object_name"]
        pose = entry["place_pose"]
        ps = pose_stamped()
        # task_fsm_server rejects a stage unless the pose is world-framed with an
        # exact identity quaternion: it compares [x, y, z, w] to [0, 0, 0, 1] as a
        # list, so an unset frame_id or a near-identity quaternion both fail.
        ps.header.frame_id = "world"
        ps.pose.position = point(x=float(pose[0]), y=float(pose[1]), z=float(pose[2]))
        ps.pose.orientation.x = 0.0
        ps.pose.orientation.y = 0.0
        ps.pose.orientation.z = 0.0
        ps.pose.orientation.w = 1.0
        st.place_pose = ps
        goal.stages.append(st)
    goal.final_empty_positions = []
    if not 1 <= len(goal.stages) <= 8:
        raise SystemExit("executor accepts 1..8 stages, plan produced %d" % len(goal.stages))
    return goal


def describe_goal(goal):
    return {"scenario_id": goal.scenario_id,
            "motion_profile_id": goal.motion_profile_id,
            "stages": [s.stage_id for s in goal.stages],
            "initial_objects": [o.object_name for o in goal.initial_objects]}


def execute(goal, run_composite, timeout_s=420.0):
    import rclpy
    from rclpy.action import ActionClient
    from rclpy.node import Node
    rclpy.init()
    node = Node("b_exec")
    try:
        client = ActionClient(node, run_composite, "run_composite")
        if not client.wait_for_server(timeout_sec=30.0):
            return {"error": "run_composite action server unavailable"}
        fut = client.send_goal_async(goal)
        rclpy.spin_until_future_complete(node, fut, timeout_sec=60.0)
        handle = fut.result()
        if handle is None or not handle.accepted:
            return {"error": "goal rejected"}
        result_fut = handle.get_result_async()
        rclpy.spin_until_future_complete(node, result_fut, timeout_sec=timeout_s)
        wrapped = result_fut.result()
        if wrapped is None:
            return {"error": "no result within %.0fs" % timeout_s}
        r = wrapped.result
        names = run_composite.Result.get_fields_and_field_types()
        return {n: getattr(r, n) for n in names
                if not hasattr(getattr(r, n), "__slots__")}
    finally:
        node.destroy_node()
        rclpy.shutdown()


def main(argv=None):
    ap = argparse.ArgumentParser(description="execute a frozen Baseline B plan")
    ap.add_argument("plan")
    ap.add_argument("out")
    args = ap.parse_args(argv)
    plan = load_plan(args.plan)
    from flexcell_interfaces.action import RunComposite
    from flexcell_interfaces.msg import CompositeStage, ObjectPosition
    from geometry_msgs.msg import Point, PoseStamped
    goal = build_goal(plan, RunComposite, CompositeStage, ObjectPosition, Point,
                      PoseStamped)
    print("  goal: " + json.dumps(describe_goal(goal)))
    result = execute(goal, RunComposite)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"goal": describe_goal(goal), "result": result}, f, indent=2,
                  default=str)
    print("  outcome=%s error_code=%s" % (result.get("outcome"), result.get("error_code")))
    print("  detail=" + str(result.get("detail"))[:160])
    return 0


if __name__ == "__main__":
    sys.exit(main())