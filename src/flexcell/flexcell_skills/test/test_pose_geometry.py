"""P2-C: the geometry utilities extracted from MoveToPose keep their contract."""
import math
import unittest
from types import SimpleNamespace as NS

from flexcell_skills import pose_geometry


def q(x=0.0, y=0.0, z=0.0, w=1.0):
    return NS(x=x, y=y, z=z, w=w)


IDENTITY = q()
HALF_Z = q(z=math.sin(math.pi / 4), w=math.cos(math.pi / 4))   # 90 deg about z


class TestNorm(unittest.TestCase):

    def test_a_unit_quaternion_has_norm_one(self):
        self.assertAlmostEqual(pose_geometry.q_norm(IDENTITY), 1.0, places=12)
        self.assertAlmostEqual(pose_geometry.q_norm(HALF_Z), 1.0, places=12)

    def test_an_unnormalised_quaternion_reports_its_norm(self):
        self.assertAlmostEqual(pose_geometry.q_norm(q(w=2.0)), 2.0, places=12)


class TestMul(unittest.TestCase):

    def test_identity_is_the_two_sided_unit(self):
        for other in (IDENTITY, HALF_Z):
            with self.subTest(other=other):
                self.assertEqual(pose_geometry.q_mul(IDENTITY, other),
                                 (other.x, other.y, other.z, other.w))
                self.assertEqual(pose_geometry.q_mul(other, IDENTITY),
                                 (other.x, other.y, other.z, other.w))

    def test_two_ninety_degree_turns_make_a_half_turn(self):
        twice = pose_geometry.q_mul(HALF_Z, HALF_Z)
        self.assertAlmostEqual(twice[2], 1.0, places=12)
        self.assertAlmostEqual(twice[3], 0.0, places=12)

    def test_the_result_is_a_plain_tuple_in_xyzw_order(self):
        out = pose_geometry.q_mul(IDENTITY, HALF_Z)
        self.assertIsInstance(out, tuple)
        self.assertEqual(len(out), 4)


class TestRotate(unittest.TestCase):

    def test_identity_leaves_a_vector_alone(self):
        self.assertEqual(pose_geometry.q_rotate(IDENTITY, (1.0, 2.0, 3.0)),
                         (1.0, 2.0, 3.0))

    def test_a_ninety_degree_z_turn_maps_x_to_y(self):
        x, y, z = pose_geometry.q_rotate(HALF_Z, (1.0, 0.0, 0.0))
        self.assertAlmostEqual(x, 0.0, places=12)
        self.assertAlmostEqual(y, 1.0, places=12)
        self.assertAlmostEqual(z, 0.0, places=12)

    def test_rotation_preserves_length(self):
        v = (0.3, -1.2, 0.7)
        out = pose_geometry.q_rotate(HALF_Z, v)
        self.assertAlmostEqual(math.hypot(*out), math.hypot(*v), places=12)


class TestAngleBetween(unittest.TestCase):

    def test_the_same_orientation_has_zero_angle(self):
        self.assertAlmostEqual(pose_geometry.q_angle_between(IDENTITY, IDENTITY),
                               0.0, places=12)

    def test_q_and_minus_q_are_the_same_orientation(self):
        # the defect this guards: an unclamped/unsigned dot would report pi
        negated = q(w=-1.0)
        self.assertAlmostEqual(
            pose_geometry.q_angle_between(IDENTITY, negated), 0.0, places=12)

    def test_a_ninety_degree_turn_reports_half_pi(self):
        self.assertAlmostEqual(
            pose_geometry.q_angle_between(IDENTITY, HALF_Z), math.pi / 2, places=12)

    def test_a_half_turn_reports_pi(self):
        half = q(z=1.0, w=0.0)
        self.assertAlmostEqual(
            pose_geometry.q_angle_between(IDENTITY, half), math.pi, places=12)


class TestCompatibility(unittest.TestCase):

    def test_the_server_still_exports_the_old_names(self):
        from flexcell_skills import move_to_pose_server as server
        for name in ("q_norm", "q_mul", "q_rotate", "q_angle_between"):
            with self.subTest(name=name):
                self.assertTrue(hasattr(server, name))
                self.assertIs(getattr(server, name),
                              getattr(pose_geometry, name))

    def test_the_module_is_pure(self):
        import ast
        from pathlib import Path
        source = Path(pose_geometry.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertEqual(imported, {"math"})


if __name__ == "__main__":
    unittest.main()
