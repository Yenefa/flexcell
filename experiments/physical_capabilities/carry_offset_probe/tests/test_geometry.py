"""Pose algebra for object_in_tcp, checked against synthetic poses."""
import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import geometry as g  # noqa: E402

IDENTITY = (0.0, 0.0, 0.0, 1.0)


def yaw(degrees):
    half = math.radians(degrees) / 2.0
    return (0.0, 0.0, math.sin(half), math.cos(half))


def pose(position, quaternion=IDENTITY):
    return (tuple(float(v) for v in position), tuple(float(v) for v in quaternion))


class OffsetTest(unittest.TestCase):
    def test_identity_frame_gives_the_raw_offset(self):
        offset = g.object_in_tcp(pose((0.1, 0.0, 0.0)), pose((0.0, 0.0, 0.0)))
        self.assertAlmostEqual(offset[0], 0.1)
        self.assertAlmostEqual(offset[1], 0.0)
        self.assertAlmostEqual(offset[2], 0.0)
        self.assertAlmostEqual(offset[6], 1.0)

    def test_object_at_the_end_effector_is_zero(self):
        ee = pose((0.3, -0.2, 0.15), yaw(37))
        self.assertLess(g.distance_mm(g.object_in_tcp(ee, ee)[:3], (0, 0, 0)), 1e-6)

    def test_yaw_rotates_the_offset_into_the_tcp_frame(self):
        # The gripper is turned 90 degrees; a world +Y offset becomes tcp +X.
        offset = g.object_in_tcp(pose((0.0, 0.1, 0.0)), pose((0, 0, 0), yaw(90)))
        self.assertAlmostEqual(offset[0], 0.1, places=9)
        self.assertAlmostEqual(offset[1], 0.0, places=9)

    def test_translation_of_the_base_does_not_change_the_relative_pose(self):
        ee = pose((1.0, 2.0, 3.0), yaw(90))
        obj = pose((1.0, 2.1, 3.0))
        offset = g.object_in_tcp(obj, ee)
        self.assertAlmostEqual(offset[0], 0.1, places=9)
        self.assertAlmostEqual(offset[1], 0.0, places=9)

    def test_round_trip_through_relative(self):
        a = pose((0.1, 0.2, 0.3), yaw(12))
        b = pose((-0.4, 0.05, 0.6), yaw(-73))
        got = g.relative(g.compose(a, b), a)
        self.assertLess(g.distance_mm(got[0], b[0]), 1e-6)
        self.assertAlmostEqual(got[1][3], b[1][3], places=9)

    def test_inverse_of_a_scaled_quaternion_is_still_a_unit_rotation(self):
        q = (0.0, 0.0, 0.6, 0.8)  # unit
        scaled = tuple(3.0 * v for v in q)
        product = g.q_mul(g.q_inv(scaled), scaled)
        self.assertAlmostEqual(product[3], 1.0, places=9)
        self.assertLess(max(abs(v) for v in product[:3]), 1e-9)

    def test_zero_quaternion_is_rejected(self):
        with self.assertRaises(ValueError):
            g.q_inv((0.0, 0.0, 0.0, 0.0))


class PackageEquivalenceTest(unittest.TestCase):
    """The probe must agree with the helpers the package already ships."""

    def setUp(self):
        root = pathlib.Path(__file__).resolve().parents[4]
        package = root / 'src/flexcell/flexcell_skills'
        if not package.is_dir():
            self.skipTest('package source not found')
        sys.path.insert(0, str(package))
        try:
            import flexcell_skills.pose_geometry as pg
        except ImportError as exc:
            self.skipTest('pose_geometry not importable: %s' % exc)
        self.pg = pg

    class Q:
        def __init__(self, values):
            self.x, self.y, self.z, self.w = values

    def test_q_mul_and_q_rotate_match(self):
        pairs = [((0.1, 0.2, 0.3, 0.9), (-0.4, 0.1, 0.2, 0.86)),
                 ((0.0, 0.0, 0.0, 1.0), (0.0, 0.6, 0.0, 0.8))]
        for a, b in pairs:
            with self.subTest(pair=(a, b)):
                self.assertAlmostEqual(
                    g.q_mul(a, b)[0],
                    self.pg.q_mul(self.Q(a), self.Q(b))[0], places=9)
                rotated_ours = g.q_rotate(a, (0.3, -0.2, 0.5))
                rotated_theirs = self.pg.q_rotate(self.Q(a), (0.3, -0.2, 0.5))
                for ours, theirs in zip(rotated_ours, rotated_theirs):
                    self.assertAlmostEqual(ours, theirs, places=9)


if __name__ == '__main__':
    unittest.main()
