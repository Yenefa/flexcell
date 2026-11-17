"""Pose algebra for the carry-offset probe.

No ROS, no package imports: the probe must stay runnable next to a recorded
sample, and the tests must run without a simulator.

Convention: a pose is ``(position, quaternion)`` where
``position = (x, y, z)`` in metres and ``quaternion = (qx, qy, qz, qw)``.
`relative(target, frame)` returns `target` expressed in `frame` coordinates,
which is what "object in tcp" means here.
"""


def q_inv(q):
    """Inverse of a (not necessarily unit) quaternion."""
    x, y, z, w = q
    norm = x * x + y * y + z * z + w * w
    if norm == 0.0:
        raise ValueError('zero quaternion has no inverse')
    return (-x / norm, -y / norm, -z / norm, w / norm)


def q_mul(a, b):
    """Hamilton product, returned as a plain (x, y, z, w) tuple."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def q_rotate(q, v):
    """Rotate the 3-vector `v` by the quaternion `q`."""
    x, y, z, w = q
    vx, vy, vz = v
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    )


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def compose(a, b):
    """T_a * T_b: apply `b`, then `a`."""
    pa, qa = a
    pb, qb = b
    return (_add(pa, q_rotate(qa, pb)), q_mul(qa, qb))


def invert(a):
    pa, qa = a
    qi = q_inv(qa)
    rotated = q_rotate(qi, pa)
    return ((-rotated[0], -rotated[1], -rotated[2]), qi)


def relative(target, frame):
    """`target` expressed in `frame` coordinates."""
    return compose(invert(frame), target)


def object_in_tcp(object_pose, ee_pose):
    """Object pose in the end-effector frame, as [x, y, z, qx, qy, qz, qw]."""
    position, quaternion = relative(object_pose, ee_pose)
    return [position[0], position[1], position[2],
            quaternion[0], quaternion[1], quaternion[2], quaternion[3]]


def distance_mm(a, b):
    """Euclidean distance between two 3-vectors, in millimetres."""
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return (dx * dx + dy * dy + dz * dz) ** 0.5 * 1000.0
