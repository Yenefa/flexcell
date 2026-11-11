#!/usr/bin/env python3
"""A procedure the runtime did not have: place relative to an ACHIEVED pose, with refinement.

WHY THIS IS A NEW SKILL AND NOT A NEW PLAN: every plan this runtime has emitted is open loop -
compute all poses from one observation, dispatch, stop. A goal anchored to where another object
ACTUALLY ended up cannot be produced that way, because the anchor carries execution error the
planner never sees. The only way to hit it is to act, measure, and act again. That loop is the
capability; the plan format cannot express it.

The loop is composed only of primitives the system already had (single-stage composite execution
plus ground-truth capture). Nothing in the skill layer changes.
"""
import math


def _dist(a, b):
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def place_relative(exec_stage, observe, reference, obj, offset, tolerance_m,
                   max_refinements=3, log=None):
    """Put obj at offset from wherever reference ACTUALLY is, refining until it holds.

    exec_stage(object_name, pose) -> None   dispatch one place, return when the robot stops
    observe() -> {name: [x, y, z]}          measure the world after the robot has stopped

    It never claims success on its own: the caller grades with the independent evaluator.
    """
    log = log if log is not None else []
    measured = observe()
    if reference not in measured:
        return {"ok": False, "why": "reference not measured", "measurements": list(measured)}
    ref_pose = measured[reference]
    target = [ref_pose[0] + float(offset[0]), ref_pose[1] + float(offset[1])]
    attempts = []
    for i in range(max_refinements + 1):
        z = target[2] if len(target) > 2 else 0.018
        exec_stage(obj, [target[0], target[1], z])
        measured = observe()
        if obj not in measured:
            attempts.append({"try": i, "error_m": None, "why": "object not measured"})
            break
        err = _dist(measured[obj], target)
        attempts.append({"try": i, "error_m": round(err, 5),
                         "target": [round(v, 4) for v in target[:2]],
                         "landed": [round(measured[obj][0], 4), round(measured[obj][1], 4)]})
        log.append(attempts[-1])
        if err <= tolerance_m:
            return {"ok": True, "tries": i + 1, "error_m": round(err, 5),
                    "attempts": attempts}
        ref_now = measured[reference]
        target = [ref_now[0] + float(offset[0]), ref_now[1] + float(offset[1])]
        bias = (measured[obj][0] - target[0], measured[obj][1] - target[1])
        target = [target[0] - bias[0], target[1] - bias[1]]
    last = attempts[-1]["error_m"] if attempts else None
    return {"ok": False, "tries": len(attempts), "error_m": last, "attempts": attempts}
