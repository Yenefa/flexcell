"""Executor-side skill post-condition verification (issue #20, M2.2-0).

A skill's declared SUCCESS is not accepted at face value: the executor
cross-checks the measured markers the skill contract promises before the
result may drive the task forward.  The motivating shape is the Week-1
PLACE ghost success: a raising execute callback makes rclpy return a
default-constructed Result whose outcome=0 reads as SUCCEEDED while every
contract marker (grasp_attached / released / has_measured_pose) stays at
its default.  The checks below turn that shape into a typed
ERR_SKILL_CONTRACT_VIOLATION failure instead of a phantom success.

Pure python, duck-typed inputs (getattr), no ROS imports: unit-testable
offline; the executor passes action Result objects (or any object with
the same fields) straight in.

Frozen contract constant: every FlexCell skill encodes success as
outcome == 0 (PickObject/PlaceObject OUTCOME_SUCCEEDED, VerifyObject
OUTCOME_VERIFIED, Observe OUTCOME_SUCCEEDED).
"""


def _dist3(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def check_pick(result):
    """PickObject.Result declared success -> grasp_attached must be true.

    Returns None when the contract holds, else a human-readable violation
    for the typed ERR_SKILL_CONTRACT_VIOLATION failure chain.
    """
    if getattr(result, 'outcome', None) != 0:
        return None
    if not getattr(result, 'grasp_attached', False):
        return ('declared SUCCEEDED but grasp_attached is not true '
                '(default-Result phantom-success shape)')
    return None


def check_place(result, place_position=None, tolerance_m=None):
    """PlaceObject.Result declared success -> released must be true and,
    when the executor supplies the commanded place position and tolerance,
    the measured object_pose_after must sit within tolerance of it."""
    if getattr(result, 'outcome', None) != 0:
        return None
    if not getattr(result, 'released', False):
        return ('declared SUCCEEDED but released is not true '
                '(default-Result phantom-success shape)')
    if place_position is not None and tolerance_m is not None:
        pose = getattr(result, 'object_pose_after', None)
        if pose is None:
            return 'declared SUCCEEDED but object_pose_after is missing'
        pos = [pose.position.x, pose.position.y, pose.position.z]
        err = _dist3(pos, place_position)
        if err > tolerance_m:
            return ('declared SUCCEEDED but object_pose_after settled %.4fm '
                    'from the commanded place pose (tolerance %.4fm)'
                    % (err, tolerance_m))
    return None


def check_verify(result):
    """VerifyObject.Result declared VERIFIED -> has_measured_pose must be
    true (a verification without a measurement is a phantom)."""
    if getattr(result, 'outcome', None) != 0:
        return None
    if not getattr(result, 'has_measured_pose', False):
        return ('declared VERIFIED but has_measured_pose is not true '
                '(default-Result phantom-success shape)')
    return None
