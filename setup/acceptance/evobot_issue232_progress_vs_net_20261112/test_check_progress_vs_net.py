#!/usr/bin/env python3
"""Tests for issue #232 tool. Every case below is one that actually bit us, or its mirror.

Run: python3 test_check_progress_vs_net.py
No simulator, no network, no archive required.
"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_progress_vs_net as C


def act(along=None, disp=None, cos=None):
    a = {}
    if along is not None:
        a["displacement_along_direction_m"] = along
    if disp is not None:
        a["displacement_m"] = disp
    if cos is not None:
        a["direction_cos"] = cos
    return a


class TestDirection(unittest.TestCase):
    def test_arbitrary_planar_direction_is_normalised(self):
        self.assertEqual(C.unit_direction([0.0, 5.0]), (0.0, 1.0))
        u = C.unit_direction([3.0, -4.0])
        self.assertAlmostEqual(u[0], 0.6)
        self.assertAlmostEqual(u[1], -0.8)

    def test_zero_and_garbage_direction_are_none(self):
        for d in ([0.0, 0.0], None, ["x", "y"], [float("nan"), 0.0], [float("inf"), 1.0]):
            self.assertIsNone(C.unit_direction(d), d)


class TestNetDisplacement(unittest.TestCase):
    def test_forward_along_minus_x(self):
        r = C.net_displacement([0.19, 0.02], [0.049713, 0.005958], (-1.0, 0.0))
        self.assertAlmostEqual(r["net_along_u_m"], 0.140287, places=6)
        self.assertEqual(r["motion"], "FORWARD")

    def test_reverse_is_negative_not_a_flipped_magnitude(self):
        # The measured failure mode: the skill reported +0.017 while the box went -0.065.
        r = C.net_displacement([0.20, 0.0], [0.20 + 0.065, 0.0], (-1.0, 0.0))
        self.assertLess(r["net_along_u_m"], 0.0)
        self.assertLess(r["net_displacement_m"], 0.0)
        self.assertAlmostEqual(r["net_displacement_m"], -0.065, places=9)
        self.assertEqual(r["motion"], "REVERSE")

    def test_lateral_dominates(self):
        r = C.net_displacement([0.20, 0.0], [0.20, 0.05], (-1.0, 0.0))
        self.assertAlmostEqual(r["net_along_u_m"], 0.0)
        self.assertAlmostEqual(r["lateral_m"], 0.05, places=9)
        self.assertEqual(r["motion"], "LATERAL")

    def test_stationary_is_below_the_reporting_floor(self):
        r = C.net_displacement([0.20, 0.0], [0.2000004, 0.0000004], (-1.0, 0.0))
        self.assertEqual(r["motion"], "STATIONARY")

    def test_diagonal_keeps_projection_and_magnitude_apart(self):
        r = C.net_displacement([0.0, 0.0], [0.03, 0.04], (1.0, 0.0))
        self.assertAlmostEqual(r["net_along_u_m"], 0.03, places=9)
        self.assertAlmostEqual(r["lateral_m"], 0.04, places=9)
        self.assertAlmostEqual(r["net_magnitude_m"], 0.05, places=9)
        # along-direction stays the projection; magnitude is reported separately
        self.assertAlmostEqual(r["net_displacement_m"], 0.03, places=9)

    def test_missing_endpoint_is_unknown_not_zero(self):
        for pre, post in ((None, [0.1, 0.1]), ([0.1, 0.1], None), (None, None)):
            r = C.net_displacement(pre, post, (-1.0, 0.0))
            self.assertEqual(r["net_displacement_m"], C.UNKNOWN)
            self.assertEqual(r["motion"], C.UNKNOWN)
            self.assertIsNotNone(r["unknown_reason"])

    def test_non_finite_endpoint_is_unknown(self):
        for bad in ([float("nan"), 0.0], [float("inf"), 0.0], ["0.1", 0.0], [True, 0.0]):
            r = C.net_displacement([0.2, 0.0], bad, (-1.0, 0.0))
            self.assertEqual(r["net_displacement_m"], C.UNKNOWN, bad)


class TestReportedProgress(unittest.TestCase):
    def test_sum_of_actions(self):
        r = C.reported_progress([act(along=0.02), act(along=0.03)], (-1.0, 0.0))
        self.assertAlmostEqual(r["reported_progress_m"], 0.05, places=9)

    def test_sign_comes_from_direction_cos_when_only_magnitude_present(self):
        r = C.reported_progress([act(disp=0.017, cos=-0.9)], (-1.0, 0.0))
        self.assertAlmostEqual(r["reported_progress_m"], -0.017, places=9)
        r2 = C.reported_progress([act(disp=0.017, cos=0.9)], (-1.0, 0.0))
        self.assertAlmostEqual(r2["reported_progress_m"], 0.017, places=9)

    def test_no_actions_is_unknown(self):
        self.assertEqual(C.reported_progress([], (-1.0, 0.0))["reported_progress_m"], C.UNKNOWN)

    def test_unusable_action_makes_the_sum_unknown_not_partial(self):
        r = C.reported_progress([act(along=0.02), {}], (-1.0, 0.0))
        self.assertEqual(r["reported_progress_m"], C.UNKNOWN)
        self.assertIn("action 1", r["unknown_reason"])

    def test_non_finite_reported_value_is_unknown(self):
        r = C.reported_progress([act(along=float("nan"))], (-1.0, 0.0))
        self.assertEqual(r["reported_progress_m"], C.UNKNOWN)


class TestThreeQuantitiesStaySeparate(unittest.TestCase):
    def test_the_4_6x_scope_case(self):
        """Measured: one action reported 0.030629, the run's net along was 0.140287."""
        r = C.analyse(pre=[0.19, 0.02], post=[0.049713, 0.005958], direction=[-1.0, 0.0],
                      actions=[act(along=0.030445808639132627)], real_travel=0.132)
        self.assertAlmostEqual(r["reported_progress_m"], 0.030445809, places=9)
        # ALONG the direction: 0.140287. This is the Lead's 0.1403.
        self.assertAlmostEqual(r["net_displacement_m"], 0.140287, places=5)
        self.assertAlmostEqual(r["net_along_u_m"], 0.140287, places=5)
        # FULL vector length is different (0.140988) and must not be substituted for it.
        self.assertAlmostEqual(r["net_magnitude_m"], 0.1409880, places=5)
        self.assertNotAlmostEqual(r["net_displacement_m"], r["net_magnitude_m"], places=5)
        self.assertAlmostEqual(r["difference_m"], 0.140287 - 0.030445809, places=5)
        self.assertGreater(r["difference_m"], 0.10)
        # ratio 4.6x is the number the Lead reported and then mis-attributed
        self.assertAlmostEqual(r["net_displacement_m"] / r["reported_progress_m"], 4.61, places=2)
        # ARM travel, not box travel: must never be read as displacement
        self.assertAlmostEqual(r["arm_travel_m"], 0.132, places=9)
        self.assertNotAlmostEqual(r["arm_travel_m"], r["net_displacement_m"], places=3)
        self.assertAlmostEqual(r["travel_to_net_ratio"], 0.132 / 0.140287, places=4)

    def test_sign_flip_differs_by_the_whole_gap(self):
        """Reported +0.017, box went -0.065: difference is -0.082, not -0.048."""
        r = C.analyse(pre=[0.20, 0.0], post=[0.265, 0.0], direction=[-1.0, 0.0],
                      actions=[act(disp=0.017, cos=1.0)])
        self.assertAlmostEqual(r["reported_progress_m"], 0.017, places=9)
        self.assertAlmostEqual(r["net_displacement_m"], -0.065, places=9)
        self.assertAlmostEqual(r["difference_m"], -0.082, places=9)
        self.assertEqual(r["motion"], "REVERSE")

    def test_unknown_propagates_to_difference(self):
        r = C.analyse(pre=None, post=[0.1, 0.1], direction=[-1.0, 0.0], actions=[act(along=0.01)])
        self.assertEqual(r["net_displacement_m"], C.UNKNOWN)
        self.assertEqual(r["difference_m"], C.UNKNOWN)
        self.assertEqual(r["status"], C.UNKNOWN)

    def test_measured_status_only_when_both_sides_known(self):
        good = C.analyse([0.2, 0.0], [0.1, 0.0], [-1.0, 0.0], [act(along=0.1)])
        self.assertEqual(good["status"], "MEASURED")
        no_actions = C.analyse([0.2, 0.0], [0.1, 0.0], [-1.0, 0.0], [])
        self.assertEqual(no_actions["status"], C.UNKNOWN)


class TestNoVerdict(unittest.TestCase):
    def test_output_has_no_pass_fail_field(self):
        r = C.analyse([0.2, 0.0], [0.1, 0.0], [-1.0, 0.0], [act(along=0.1)])
        for forbidden in ("passed", "pass", "success", "verdict", "ok"):
            self.assertNotIn(forbidden, r)


if __name__ == "__main__":
    unittest.main(verbosity=2)
