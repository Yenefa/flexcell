"""Checkpoint cadence for the registered 30 mm finger stroke."""

# Both cadences reserve two approach goals and two goals for unloading and return.
_STANDARD_CHECKPOINTS = tuple(range(1, 10))
_COMPACT_CHECKPOINTS = (1, 2, 4, 6, 8, 9)
STANDARD_MOTION_GOALS = len(_STANDARD_CHECKPOINTS) + 4
COMPACT_MOTION_GOALS = len(_COMPACT_CHECKPOINTS) + 4


def stroke_checkpoints(distance_m, motion_limit):
    """Return cumulative distances along the registered straight stroke.

    The compact cadence preserves the first two 4 mm steps for contact
    acquisition, then uses at most 8 mm between observations. Both end at the
    same overtravel cap. Each segment still needs a checked trajectory.
    """
    if motion_limit == COMPACT_MOTION_GOALS:
        checkpoints = _COMPACT_CHECKPOINTS
    elif motion_limit == STANDARD_MOTION_GOALS:
        checkpoints = _STANDARD_CHECKPOINTS
    else:
        raise ValueError('unsupported contact stroke motion limit')
    return tuple(min(step * .004, distance_m + .005) for step in checkpoints)
