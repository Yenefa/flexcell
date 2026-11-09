"""Safe planned-trajectory summary (M2.3 audit P0-1 fix).

The MoveToPose executor indexed ``traj.joint_trajectory.points[-1]`` BEFORE
its own ``npts == 0`` guard - an empty planner trajectory escaped ``_execute``
as an unhandled IndexError, and rclpy's fallback default Result (outcome=0)
reported it as OUTCOME_SUCCEEDED: the same ghost-success class as the Week-1
PLACE bug fixed in M2.2 Step 0, on the one server the crash-guard sweep had
missed.  This module is pure python (no rclpy) so the guard is offline
testable.
"""

import math


def validate_arm_trajectory(trajectory):
    """Validate an MTC arm trajectory before its private executor handoff."""
    names = list(trajectory.joint_names)
    if set(names) != {'joint1', 'joint2', 'joint3', 'joint4'} or len(names) != 4 or not trajectory.points:
        raise ValueError('MTC must return exactly four unique arm joints')
    previous = -1
    for point in trajectory.points:
        stamp = point.time_from_start.sec * 10**9 + point.time_from_start.nanosec
        values = list(point.positions) + list(point.velocities) + list(point.accelerations)
        if (len(point.positions) != 4 or stamp <= previous or stamp < 0
                or not all(math.isfinite(v) for v in values)
                or len(point.velocities) not in (0, 4)
                or len(point.accelerations) not in (0, 4)):
            raise ValueError('invalid MTC trajectory point')
        previous = stamp
    if previous <= 0:
        raise ValueError('zero-duration MTC trajectory')


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
