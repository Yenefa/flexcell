#!/usr/bin/env python3
"""Run the closed-loop push recovery against one live world.

This is the live half of the push_recover skill: the policy module decides, this file acts.
Split deliberately, so the decision logic is unit tested without ROS and this file stays a
thin loop that is easy to read when a real run misbehaves.

Comparability with the single-shot baseline is the whole point, so the request is the same
distance the earlier repeats asked for (0.09 m) and the only change is that a short push with
contact lost is followed by another request for the shortfall.
"""
import json
import os
import subprocess
import sys

WT = "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp"
sys.path.insert(0, os.path.join(WT, "src/flexcell/flexcell_skills"))
sys.path.insert(0, os.path.join(WT, "src/flexcell/flexcell_skills/flexcell_skills/contracts"))

import push_recover as R  # noqa: E402


def send_push(node_and_client, object_name, distance_m, contact_z):
    import rclpy
    from flexcell_interfaces.action import PushObject
    node, client = node_and_client
    goal = PushObject.Goal()
    goal.request_id = "recover-%s" % object_name
    goal.object_name = object_name
    goal.direction.x = -1.0
    goal.direction.y = 0.0
    goal.direction.z = 0.0
    goal.distance_m = float(distance_m)
    goal.contact_height_m = float(contact_z)
    goal.overdrive_m = float("nan")
    future = client.send_goal_async(goal)
    rclpy.spin_until_future_complete(node, future, timeout_sec=60.0)
    handle = future.result()
    if handle is None or not handle.accepted:
        return {"error": "goal rejected"}
    result_future = handle.get_result_async()
    rclpy.spin_until_future_complete(node, result_future, timeout_sec=240.0)
    wrapped = result_future.result()
    if wrapped is None:
        return {"error": "no result"}
    r = wrapped.result
    fields = PushObject.Result.get_fields_and_field_types()
    return {n: getattr(r, n) for n in fields if not hasattr(getattr(r, n), "__slots__")}


def _target_from_spec(spec):
    """Derive how far to push from the task's own geometry.

    THE LITERAL 0.09 THAT USED TO BE HERE HAD NO RELATION TO THE TASK. The T08 spec
    does not ask for a 90 mm push; it asks for target_box_a to end up inside
    zone_push, which is a disc of radius 0.06 centred at x=0.12, with the box
    starting at x=0.22. Any displacement that lands the box centre on that disc
    satisfies the task, i.e. anything from about 0.04 to 0.16 m. The hardcoded 0.09
    happened to fall inside that window and was then treated as a requirement.

    Measured consequence, from this repository's own archived evidence: on
    U_shot/seed3002 the push moved the box 0.0306 m, the frozen evaluator returned
    passed=True because 0.0306 clears its 0.030 floor, and the recovery layer
    nonetheless reported "short by 0.0596 m" against 0.09 - it wanted to push a
    further 60 mm that the task never asked for.

    Only public task geometry is used here: object initial poses and zone poses.
    expected_goal is deliberately NOT read, because min_displacement_m and
    max_displacement_m there are the evaluator's acceptance bounds, and a recovery
    policy that reads them would be fitting itself to the answer key.
    """
    import math as _m
    obj = spec["objects"][0]
    zone = spec["zones"][0]
    box = [float(v) for v in obj["initial_pose"]]
    centre = [float(v) for v in zone["pose"]]
    radius = float(zone["radius"])
    # Distance that brings the box centre onto the zone centre: maximum margin
    # inside the disc, and independent of the evaluator's tolerance band.
    return _m.hypot(box[0] - centre[0], box[1] - centre[1]), radius, centre


RECOVERY_MODES = ("centre", "enter")


def _target_for_mode(spec, mode):
    """Two defensible objectives, exposed so the difference can be measured.

    centre - push until the box centre reaches the zone centre. Maximum margin
             inside the disc, at the cost of re-pushing runs that an evaluator
             reading only "is the box inside the zone" would already accept.
    enter  - push only until the box centre is within the zone radius. Matches the
             evaluator's intent and stops earlier, but parks the box near the
             acceptance boundary where measurement noise can put it back outside.

    Neither is chosen here. The mode must be named explicitly.
    """
    if mode not in RECOVERY_MODES:
        raise ValueError("recovery mode must be one of %r, got %r" % (RECOVERY_MODES, mode))
    to_centre, radius, centre = _target_from_spec(spec)
    if mode == "centre":
        return to_centre, radius, centre
    return max(0.0, to_centre - radius), radius, centre


def main(argv):
    task_path, outdir, contact_z, max_attempts = argv[1], argv[2], float(argv[3]), int(argv[4])
    mode = argv[5] if len(argv) > 5 else "centre"
    spec = json.load(open(task_path, encoding="utf-8"))
    target_object = spec["objects"][0]["name"]
    target_m, zone_radius, zone_centre = _target_for_mode(spec, mode)
    print("  mode=%s target from task geometry: %.4f m (zone centre %s, radius %.3f)"
          % (mode, target_m, zone_centre[:2], zone_radius))

    import rclpy
    from rclpy.action import ActionClient
    from rclpy.node import Node
    from flexcell_interfaces.action import PushObject

    rclpy.init()
    node = Node("push_recovery")
    client = ActionClient(node, PushObject, "push_object")
    attempts = []
    if client.wait_for_server(timeout_sec=30.0):
        achieved = 0.0
        for attempt in range(max_attempts):
            action, payload = R.choose_next_request(target_m, achieved, len(attempts),
                                                    max_attempts - len(attempts))
            if action != "push":
                print("  policy stopped: %s %s" % (action, payload))
                break
            print("  attempt %d: asking for %.4f m" % (attempt + 1, payload["distance_m"]))
            result = send_push((node, client), target_object, payload["distance_m"], contact_z)
            json.dump(result, open(os.path.join(outdir, "push_%02d.json" % attempt), "w"),
                      indent=2, default=str)
            attempts.append(result)
            made, moved, carry, problem = R.classify_attempt(result)
            print("    moved %.4f m contact=%s carry=%s %s"
                  % (moved, made, carry, problem or ""))
            achieved += moved
            if carry:
                break
            if not R.is_progress(moved) and attempt > 0:
                print("    no meaningful progress, stopping recovery")
                break
    else:
        print("  PUSH SERVER UNAVAILABLE")
    node.destroy_node()
    rclpy.shutdown()

    verdict = R.accumulate(attempts, target_m)
    json.dump({"verdict": verdict, "attempts": attempts},
              open(os.path.join(outdir, "recovery.json"), "w"), indent=2, default=str)
    print("  recovery outcome=%s achieved=%.4f m attempts=%d"
          % (verdict["outcome"], verdict["achieved_m"], verdict["attempts"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
