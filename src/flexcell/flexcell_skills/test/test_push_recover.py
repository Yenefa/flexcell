"""Tests for the closed-loop push recovery policy.

These are pure-policy tests: no ROS, no simulator. The policy is where the capability lives,
so it is where the tests belong. The live controller is a thin loop around accumulate().

The measured failure this addresses: PushObject stops at the first increment that fails to
move the object, which on this robot happens after 20-30 mm of a 30 mm target.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "flexcell_skills", "contracts"))

import push_recover as R  # noqa: E402


def res(displacement, contact_made=True, carry=False):
    return {"displacement_m": displacement, "contact_made": contact_made,
            "carry_engaged_during": carry}


# ------------------------------------------------------------ reach logic

def test_a_single_successful_attempt_reaches():
    verdict = R.accumulate([res(0.032)], 0.030)
    assert verdict["outcome"] == R.OUTCOME_REACHED
    assert verdict["attempts"] == 1


def test_two_partial_attempts_add_up():
    """The real case: 0.020 then 0.015 is a pass, though neither alone is."""
    verdict = R.accumulate([res(0.020), res(0.015)], 0.030)
    assert verdict["outcome"] == R.OUTCOME_REACHED
    assert verdict["attempts"] == 2
    assert verdict["achieved_m"] >= 0.030


def test_the_measured_shortfall_needs_more_than_one_attempt():
    """28.55 mm against a 30 mm target: the old skill reported failure here."""
    verdict = R.accumulate([res(0.02855)], 0.030)
    assert verdict["outcome"] == R.OUTCOME_BUDGET_EXHAUSTED
    assert verdict["achieved_m"] < 0.030


# ------------------------------------------------------------ stop rules

def test_carry_engaged_stops_immediately():
    verdict = R.accumulate([res(0.005), res(0.010, carry=True), res(0.050)], 0.030)
    assert verdict["outcome"] == R.OUTCOME_CARRY_ENGAGED
    assert verdict["attempts"] == 2, "must stop at the carrying attempt, not continue"


def test_no_contact_ever_is_its_own_failure():
    verdict = R.accumulate([res(0.0, contact_made=False),
                            res(0.001, contact_made=False)], 0.030)
    assert verdict["outcome"] == R.OUTCOME_NO_CONTACT


def test_contact_then_no_progress_exhausts_the_budget():
    verdict = R.accumulate([res(0.010), res(0.0), res(0.0)], 0.030)
    assert verdict["outcome"] == R.OUTCOME_BUDGET_EXHAUSTED
    assert "short by" in verdict["detail"]


def test_an_unreadable_result_is_not_counted_as_success():
    made, moved, carry, problem = R.classify_attempt({"nonsense": True})
    assert made is False
    assert moved == 0.0
    assert carry is False
    assert problem == "displacement missing"


def test_a_non_finite_displacement_is_refused():
    made, moved, _carry, problem = R.classify_attempt({"displacement_m": float("nan"),
                                                       "contact_made": True})
    assert made is False
    assert problem == "displacement not finite"


def test_a_negative_displacement_is_refused():
    """A backward move must not count toward the target.

    The reason is now specific rather than generic: a negative signed projection means the
    object went the wrong way, which is a different diagnosis from an unreadable value.
    """
    _made, moved, _carry, problem = R.classify_attempt({"displacement_m": -0.002,
                                                        "contact_made": True})
    assert moved == 0.0
    assert problem == "object moved backwards"


# ------------------------------------------------------- request shaping

def test_the_next_request_asks_for_the_shortfall_only():
    action, payload = R.choose_next_request(target_m=0.030, achieved_m=0.020,
                                            attempted_m=2, remaining_attempts=3)
    assert action == "push"
    assert abs(payload["distance_m"] - 0.010) < 1e-9


def test_no_request_is_made_once_the_target_is_met():
    action, _ = R.choose_next_request(0.030, 0.030, 1, 3)
    assert action == "reached"


def test_no_request_is_made_with_no_budget_left():
    action, payload = R.choose_next_request(0.030, 0.010, 3, 0)
    assert action == "exhausted"
    assert "no attempts left" in payload["reason"]


def test_a_non_positive_target_is_refused_rather_than_looping():
    action, _ = R.choose_next_request(0.0, 0.0, 0, 5)
    assert action == "reached"


# --------------------------------------------------------------- progress

def test_tiny_motion_does_not_justify_another_approach():
    assert R.is_progress(0.0005) is False


def test_real_motion_does():
    assert R.is_progress(0.020) is True


def test_nan_is_not_progress():
    assert R.is_progress(float("nan")) is False


# ------------------------------------------------------- the whole point

def test_a_backward_move_is_not_counted_as_progress():
    """The bug a real run exposed.

    displacement_m is an unsigned magnitude, so a block flicked backwards looks like motion.
    The policy must read the signed projection. Three of five live trials regressed because
    it did not: the block ended at x=0.29, 0.36 and 0.41 from a start of 0.22.
    """
    made, moved, carry, problem = R.classify_attempt({
        "displacement_along_direction_m": -0.0735,
        "displacement_m": 0.0735,
        "contact_made": True,
    })
    assert moved == 0.0
    assert problem == "object moved backwards"
    assert made is True, "contact did happen; the object simply went the wrong way"


def test_the_signed_field_is_preferred_over_the_magnitude():
    made, moved, _c, problem = R.classify_attempt({
        "displacement_along_direction_m": 0.0310,
        "displacement_m": 0.0312,
        "contact_made": True,
    })
    assert moved == 0.0310, "the projection, not the magnitude"
    assert problem is None


def test_a_backward_move_does_not_accumulate_toward_the_target():
    verdict = R.accumulate([{"displacement_along_direction_m": -0.05,
                             "displacement_m": 0.05, "contact_made": True}], 0.030)
    assert verdict["outcome"] == R.OUTCOME_BUDGET_EXHAUSTED
    assert verdict["achieved_m"] == 0.0


def test_recovery_converts_the_measured_failure_into_a_pass():
    """The end-to-end claim, stated as a test.

    Three measured single-shot results on this robot: 23.02, 28.55, 23.26 mm against a 30 mm
    target. Composed as successive attempts with the recovery policy, the budget is met.
    """
    measured = [0.02302, 0.02855, 0.02326]
    achieved = 0.0
    attempts = []
    for moved in measured:
        attempts.append(res(moved))
        achieved += moved
        if achieved >= 0.030:
            break
    verdict = R.accumulate(attempts, 0.030)
    assert verdict["outcome"] == R.OUTCOME_REACHED
    assert verdict["achieved_m"] >= 0.030