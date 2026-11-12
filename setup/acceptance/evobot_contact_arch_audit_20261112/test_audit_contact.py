"""Synthetic frame checks; these are not robot capability evidence."""
import math
import unittest

from audit_contact import ee, pitch, rotate


class FrameChecks(unittest.TestCase):
    def assertPoint(self, actual, expected):
        for a,b in zip(actual,expected):
            self.assertAlmostEqual(a,b,places=12)

    def test_parent_translation_is_not_the_ee_position(self):
        self.assertPoint(ee([.1,0.,.2,0.,0.,0.,1.]), [.226,0.,.2])

    def test_quarter_turn_pitch_rotates_the_fixed_offset_downward(self):
        s = math.sqrt(.5)
        self.assertPoint(ee([.1,0.,.2,0.,s,0.,s]), [.1,0.,.074])

    def test_yaw_rotates_the_tool_offset_into_world_y(self):
        s = math.sqrt(.5)
        self.assertPoint(ee([.1,0.,.2,0.,0.,s,s]), [.1,.126,.2])

    def test_object_inverse_rotation_recovers_the_known_surface_point(self):
        q = [0.,math.sin(.4),0.,math.cos(.4)]
        point = [.01,.002,.0175]
        world = rotate(q,point)
        self.assertPoint(rotate([-q[0],-q[1],-q[2],q[3]],world),point)

    def test_antipodal_quaternions_have_identical_physical_pose(self):
        q = [0.,math.sin(.4),0.,math.cos(.4)]
        self.assertPoint(rotate(q,[.1,.2,.3]),rotate([-v for v in q],[.1,.2,.3]))
        self.assertAlmostEqual(pitch(q),pitch([-v for v in q]))


if __name__ == '__main__':
    unittest.main()
