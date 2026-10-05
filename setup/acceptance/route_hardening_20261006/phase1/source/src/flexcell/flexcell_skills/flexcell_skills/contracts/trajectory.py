"""Safe planned-trajectory summary (M2.3 audit P0-1 fix).

The MoveToPose executor indexed ``traj.joint_trajectory.points[-1]`` BEFORE
its own ``npts == 0`` guard - an empty planner trajectory escaped ``_execute``
as an unhandled IndexError, and rclpy's fallback default Result (outcome=0)
reported it as OUTCOME_SUCCEEDED: the same ghost-success class as the Week-1
PLACE bug fixed in M2.2 Step 0, on the one server the crash-guard sweep had
missed.  This module is pure python (no rclpy) so the guard is offline
testable.
"""


def trajectory_summary(traj):
    """(npts, final_positions, duration_s) from a planned trajectory.

    Never raises.  ``npts == 0`` or ``final_positions is None`` means "not a
    usable trajectory" - the caller must refuse it with a typed failure and
    never index into it.
    """
    try:
        points = list(traj.joint_trajectory.points)
    except Exception:  # noqa: BLE001 - malformed trajectory object
        return 0, None, None
    if not points:
        return 0, None, None
    try:
        last = points[-1]
        t = last.time_from_start
        duration = float(t.sec) + float(t.nanosec) * 1e-9
        final = list(last.positions)
    except Exception:  # noqa: BLE001 - points present but unreadable
        return len(points), None, None
    return len(points), final, duration
