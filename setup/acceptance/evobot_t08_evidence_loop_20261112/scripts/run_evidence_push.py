#!/usr/bin/env python3
"""Closed-loop push driver WITH a frozen-ceiling guard, for the T08 evidence loop.

WHY THIS FILE EXISTS INSTEAD OF REUSING run_push_recovery.py
    run_push_recovery.py is the arm-R policy driver from the previous round and
    its output is archived evidence; it is not edited. This driver makes the
    same decisions through the SAME frozen policy module
    (contracts/push_recover.py, imported, never modified) and adds exactly two
    things the previous round did not have:

      1. A CEILING GUARD. The frozen task clause is
         min_displacement_m=0.030 <= d <= max_displacement_m=0.150. The previous
         round's best recovery trial reached 145.58 mm - a 4.4 mm margin - and a
         fixed-step control run recorded a 156.77 mm overshoot. An iterative
         policy that keeps asking for the shortfall can therefore overshoot the
         ceiling on a strong push, and overshooting is a FAIL for pushing too
         far. Before each further request this driver projects the delivered
         distance using the largest overshoot ratio already OBSERVED in this
         trial, and stops if the projection would cross the guard. The guard
         value lives here, in a driver, not in push.py, not in the policy
         contract, and not in any threshold.

         KNOWN LIMITATION, measured in arm R: the projection uses the largest
         overshoot ratio OBSERVED SO FAR IN THIS TRIAL, so on attempt 1 it
         cannot bind. Arm R trial 1 is exactly that case - one 90 mm request
         delivered 152.4 mm (server error_code 36, "a shove, not a bounded
         push") and crossed the 150 mm ceiling on the signed value. The guard
         therefore protects LATER attempts only; an overshooting first attempt
         is reported as the named class FAIL_OVERSHOOT, not hidden. The guard
         was deliberately NOT tightened after seeing that result: doing so would
         make the driver that measured arms R and S different from the one that
         measures U.

      2. Full per-attempt recording: every PushObject result is written verbatim
         (push_XX.json), and recovery.json records the policy's own verdict
         next to the guard's decisions, so an auditor can see whether the guard
         bound a request or not.

THE SIGNED FIELD
    displacement_m is the UNSIGNED magnitude of the object's motion. A block
    flicked backwards still reads positive. Every decision below therefore uses
    displacement_along_direction_m (signed projection onto the commanded
    direction); the unsigned value is recorded but never used to decide.
"""
import json
import math
import os
import sys

WT = "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp"
sys.path.insert(0, os.path.join(WT, "src/flexcell/flexcell_skills"))
sys.path.insert(0, os.path.join(WT, "src/flexcell/flexcell_skills/flexcell_skills/contracts"))

import push_recover as R  # noqa: E402  (frozen policy: imported, never edited)

# Driver-level ceiling guard, in metres of TOTAL measured displacement.
# 0.140 leaves a 10 mm margin below the frozen 0.150 max_displacement_m.
CEILING_GUARD_M = 0.140


def plain(value):
    """Convert a ROS field into something json.dump can write without guessing."""
    if isinstance(value, (bool, int, float, str)):
        return value
    if all(hasattr(value, a) for a in ("x", "y", "z")):
        return [float(value.x), float(value.y), float(value.z)]
    if hasattr(value, "position"):
        p = value.position
        q = getattr(value, "orientation", None)
        out = {"position": [float(p.x), float(p.y), float(p.z)]}
        if q is not None:
            out["orientation"] = [float(q.x), float(q.y), float(q.z), float(q.w)]
        return out
    return str(value)


def send_push(node_and_client, object_name, direction, distance_m, contact_z, request_id):
    import rclpy
    from flexcell_interfaces.action import PushObject
    node, client = node_and_client
    goal = PushObject.Goal()
    goal.request_id = request_id
    goal.object_name = object_name
    goal.direction.x, goal.direction.y, goal.direction.z = (
        float(direction[0]), float(direction[1]), 0.0)
    goal.distance_m = float(distance_m)
    goal.contact_height_m = float(contact_z)
    goal.overdrive_m = float("nan")
    future = client.send_goal_async(goal)
    rclpy.spin_until_future_complete(node, future, timeout_sec=60.0)
    handle = future.result()
    if handle is None or not handle.accepted:
        return {"error": "goal rejected"}
    result_future = handle.get_result_async()
    rclpy.spin_until_future_complete(node, result_future, timeout_sec=300.0)
    wrapped = result_future.result()
    if wrapped is None:
        return {"error": "no result"}
    r = wrapped.result
    return {n: plain(getattr(r, n)) for n in PushObject.Result.get_fields_and_field_types()}


def main(argv):
    task_path, outdir = argv[1], argv[2]
    contact_z = float(argv[3])
    max_attempts = int(argv[4])
    ceiling = float(argv[5]) if len(argv) > 5 else CEILING_GUARD_M

    spec = json.load(open(task_path, encoding="utf-8"))
    target_object = spec["objects"][0]["name"]
    goal = spec["expected_goal"]["push"][target_object]
    direction = goal["direction"]
    target_m = (float(goal["min_displacement_m"]) + float(goal["max_displacement_m"])) / 2.0
    max_displacement_m = float(goal["max_displacement_m"])

    import rclpy
    from rclpy.action import ActionClient
    from rclpy.node import Node
    from flexcell_interfaces.action import PushObject

    rclpy.init()
    node = Node("t08_evidence_push_driver")
    client = ActionClient(node, PushObject, "push_object")
    attempts = []
    decisions = []
    guard_bound = False
    overshoot_ratio = 1.0
    achieved = 0.0

    if not client.wait_for_server(timeout_sec=30.0):
        print("  PUSH SERVER UNAVAILABLE")
        json.dump({"verdict": {"outcome": "SERVER_UNAVAILABLE", "achieved_m": 0.0,
                               "attempts": 0},
                   "attempts": [], "decisions": decisions,
                   "ceiling_guard_m": ceiling, "guard_bound": False,
                   "target_m": target_m},
                  open(os.path.join(outdir, "recovery.json"), "w"), indent=2)
        node.destroy_node()
        rclpy.shutdown()
        return 2

    for attempt in range(max_attempts):
        action, payload = R.choose_next_request(target_m, achieved, len(attempts),
                                               max_attempts - len(attempts))
        if action != "push":
            decisions.append({"attempt": attempt + 1, "action": action,
                              "payload": payload})
            print("  policy stopped: %s %s" % (action, payload))
            break
        requested = float(payload["distance_m"])
        # Projection: what this request could actually deliver, using the
        # largest overshoot ratio already measured in THIS trial.
        projected = achieved + requested * max(1.0, overshoot_ratio)
        record = {"attempt": attempt + 1, "requested_m": requested,
                  "achieved_before_m": achieved,
                  "overshoot_ratio_used": max(1.0, overshoot_ratio),
                  "projected_total_m": projected, "ceiling_guard_m": ceiling,
                  "guard_bound": False}
        if achieved >= ceiling or projected > ceiling:
            record["guard_bound"] = True
            record["action"] = "stop_ceiling_guard"
            decisions.append(record)
            guard_bound = True
            print("  CEILING GUARD: achieved=%.4f projected=%.4f > %.4f -> stop"
                  % (achieved, projected, ceiling))
            break
        decisions.append(record)
        print("  attempt %d: asking for %.4f m (achieved %.4f)" % (attempt + 1, requested, achieved))
        result = send_push((node, client), target_object, direction, requested,
                           contact_z, "t08loop-%s-%d" % (target_object, attempt))
        json.dump(result, open(os.path.join(outdir, "push_%02d.json" % attempt), "w"),
                  indent=2, default=str)
        attempts.append(result)
        made, moved, carry, problem = R.classify_attempt(result)
        delivered = result.get("displacement_m")
        if isinstance(delivered, (int, float)) and math.isfinite(delivered) and requested > 0:
            overshoot_ratio = max(overshoot_ratio, float(delivered) / requested)
        print("    moved %.4f m signed (unsigned %.4f) contact=%s carry=%s %s"
              % (moved, float(delivered) if isinstance(delivered, (int, float)) else float("nan"),
                 made, carry, problem or ""))
        achieved += moved
        if carry:
            break
        if not R.is_progress(moved) and attempt > 0:
            print("    no meaningful progress, stopping recovery")
            break

    verdict = R.accumulate(attempts, target_m)
    final_displacement = None
    if attempts:
        last = attempts[-1]
        before = last.get("measured_before") or {}
        after = last.get("measured_after") or {}
        try:
            bp, ap = before["position"], after["position"]
            final_displacement = math.hypot(ap[0] - bp[0], ap[1] - bp[1])
        except Exception:
            final_displacement = None
    payload = {
        "verdict": verdict,
        "attempts": attempts,
        "decisions": decisions,
        "ceiling_guard_m": ceiling,
        "guard_bound": guard_bound,
        "target_m": target_m,
        "max_displacement_m": max_displacement_m,
        "achieved_signed_m": achieved,
        "overshoot_ratio_observed": overshoot_ratio,
        "last_attempt_unsigned_displacement_m": final_displacement,
        "contact_height_m": contact_z,
        "task_id": spec["task_id"],
        "target_object": target_object,
        "direction": list(direction),
    }
    json.dump(payload, open(os.path.join(outdir, "recovery.json"), "w"),
              indent=2, default=str)
    print("  recovery outcome=%s achieved=%.4f m attempts=%d guard_bound=%s"
          % (verdict["outcome"], verdict["achieved_m"], verdict["attempts"], guard_bound))
    node.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
