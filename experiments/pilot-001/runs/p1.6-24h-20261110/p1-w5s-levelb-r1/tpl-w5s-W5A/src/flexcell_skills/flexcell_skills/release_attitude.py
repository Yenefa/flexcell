#!/usr/bin/env python3
"""Pure-python pre-release attitude gate for the attached-object PLACE path.

Issue #121 found that a box released with its local Z tilted away from world
Z tips over on landing: the horizontal shift is almost exactly
``h * (1 - cos(tilt) + sin(tilt))`` for the 35 mm cube, and the measured
shift direction aligned with the tilt direction in 72/72 usable historical
releases. The existing pre-release gate only checks position.

This module has no ROS dependency so the geometry can be unit-tested offline.
It is deliberately fail-closed: an unavailable, malformed or non-finite
quaternion is refused rather than guessed.

The gate is OPT-IN: place_server declares ``max_release_tilt_deg`` with a
default of -1 (disabled), and refuses a configuration that declares a limit on
a path which cannot level the release (the level solver only exists on the mtc
place backend with the detachable_joint carry). Profiles that declare the
level contract set the gate to the same number the solver targets; profiles
that declare nothing keep the pre-#121 behaviour exactly. The 20 deg constant
below is the reference ceiling used by the unit tests and by callers that do
not pass an explicit limit - it is not a default any more.
"""

import math

DEFAULT_MAX_RELEASE_TILT_DEG = 20.0


def up_vector(q):
    """Box local +Z in world frame for a (x, y, z, w) quaternion."""
    if q is None or len(q) != 4:
        raise ValueError('quaternion must have four components')
    x, y, z, w = (float(v) for v in q)
    n = math.sqrt(x * x + y * y + z * z + w * w)
    if not math.isfinite(n) or n <= 0.0:
        raise ValueError('quaternion has zero or non-finite norm')
    x, y, z, w = x / n, y / n, z / n, w / n
    return (2.0 * (x * z + w * y),
            2.0 * (y * z - w * x),
            1.0 - 2.0 * (x * x + y * y))


def tilt_deg(q):
    """Angle between box local +Z and world +Z. Yaw about Z contributes zero."""
    _, _, uz = up_vector(q)
    return math.degrees(math.acos(max(-1.0, min(1.0, uz))))


def attitude_gate(q, max_deg=DEFAULT_MAX_RELEASE_TILT_DEG):
    """Return (ok, detail). Refuse rather than guess on bad input."""
    try:
        tilt = tilt_deg(q)
    except (ValueError, TypeError, ZeroDivisionError, OverflowError):
        return False, 'release attitude unavailable: invalid quaternion'
    if not math.isfinite(tilt):
        return False, 'release attitude unavailable: nonfinite tilt'
    if not math.isfinite(max_deg) or max_deg < 0.0:
        return False, 'release attitude unavailable: invalid tilt limit'
    if tilt > max_deg:
        return False, ('release tilt %.3f deg exceeds %.1f deg limit; carry held'
                       % (tilt, max_deg))
    return True, 'release tilt %.3f deg within %.1f deg' % (tilt, max_deg)
