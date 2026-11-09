"""Pure quaternion helpers extracted from MoveToPose (P2-C, first slice).

These are the geometry utilities the action server used to define inline. They
touch no ROS message type and hold no state: every function reads `.x/.y/.z/.w`
duck-typed, so a geometry_msgs Quaternion, a plain object or a test double all
work. Moving them here gives them their own tests and keeps the server to its
listed responsibilities (validation, admission, lifecycle, cancellation) - the
cancellation mechanics are deliberately NOT touched.
"""
import math


def q_norm(q):
    return math.sqrt(q.x * q.x + q.y * q.y + q.z * q.z + q.w * q.w)


def q_mul(a, b):
    """Hamilton product, returned as a plain (x, y, z, w) tuple."""
    return (
        a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y,
        a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x,
        a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w,
        a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z,
    )


def q_rotate(q, v):
    """Rotate the 3-vector `v` by the unit quaternion `q`."""
    x, y, z, w = q.x, q.y, q.z, q.w
    vx, vy, vz = v
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    )


def q_angle_between(a, b):
    """Unsigned angle (radians) between two quaternion orientations.

    The dot product is clamped and taken absolute, so q and -q (the same
    orientation) give 0 rather than pi.
    """
    d = a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w
    d = max(-1.0, min(1.0, abs(d)))
    return 2.0 * math.acos(d)
