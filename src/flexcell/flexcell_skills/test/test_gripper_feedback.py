"""P1-D: a completed GripperCommand is not evidence that an object was grasped."""
import unittest
from types import SimpleNamespace as NS

from flexcell_skills.common import gripper_outcome


def result(reached=False, stalled=False, position=None, effort=None):
    return NS(reached_goal=reached, stalled=stalled, position=position,
              effort=effort)


class TestGripperOutcome(unittest.TestCase):

    def test_reached_goal_is_a_grasp_at_goal(self):
        doc = gripper_outcome(result(reached=True, position=0.001), requested=0.0)
        self.assertEqual(doc["classification"], "GRASPED_AT_GOAL")
        self.assertTrue(doc["reached_goal"])

    def test_stalled_is_classified_separately_from_a_reached_goal(self):
        doc = gripper_outcome(result(stalled=True, position=0.017), requested=0.0)
        self.assertEqual(doc["classification"], "GRASP_STALLED")
        self.assertFalse(doc["reached_goal"])
        self.assertTrue(doc["stalled"])
        self.assertAlmostEqual(doc["aperture_error"], 0.017, places=6)

    def test_no_contact_when_neither_flag_is_set_and_the_aperture_is_far(self):
        doc = gripper_outcome(result(position=0.02), requested=0.0)
        self.assertEqual(doc["classification"], "NO_CONTACT")

    def test_a_matching_aperture_counts_as_reached_even_without_the_flag(self):
        doc = gripper_outcome(result(position=0.0205), requested=0.02)
        self.assertEqual(doc["classification"], "GRASPED_AT_GOAL")

    def test_no_measured_aperture_is_unmeasured_not_a_failed_grasp(self):
        # a controller that reports neither a flag nor a position is silent,
        # not proof of a failed grasp: the physical check still decides.
        doc = gripper_outcome(result(), requested=0.0)
        self.assertEqual(doc["classification"], "UNMEASURED")
        self.assertNotEqual(doc["classification"], "NO_CONTACT")

    def test_missing_result_is_unknown_not_success(self):
        doc = gripper_outcome(None, requested=0.0)
        self.assertEqual(doc["classification"], "UNKNOWN")
        self.assertFalse(doc["reached_goal"])

    def test_measured_values_are_preserved_for_the_episode(self):
        doc = gripper_outcome(result(stalled=True, position=0.0175, effort=9.5),
                              requested=0.0)
        self.assertAlmostEqual(doc["position"], 0.0175, places=6)
        self.assertAlmostEqual(doc["effort"], 9.5, places=6)

    def test_release_that_never_opened_is_visible(self):
        # the place path compares the measured aperture against the request
        doc = gripper_outcome(result(stalled=True, position=0.001),
                              requested=0.02, aperture_tolerance_m=0.005)
        self.assertGreater(doc["aperture_error"], 0.005)
        self.assertFalse(doc["reached_goal"])

    def test_a_real_release_passes_the_same_check(self):
        doc = gripper_outcome(result(reached=True, position=0.02),
                              requested=0.02, aperture_tolerance_m=0.005)
        self.assertLessEqual(doc["aperture_error"], 0.005)
        self.assertTrue(doc["reached_goal"])


if __name__ == "__main__":
    unittest.main()
