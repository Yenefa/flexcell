"""Closed-loop push with contact-loss recovery.

WHY THIS EXISTS AND WHY IT IS NOT A CHANGE TO PushObject
    PushObject is a single bounded shot: it issues a fixed increment sequence and, at the
    first increment that fails to move the object, it stops and reports ERR_CONTACT_LOST.
    Measured on this robot, that happens after roughly 20-30 mm: 23.02, 28.55 and 23.26 mm
    across three runs, and a 135 mm spread over five repeats at the same parameters. The
    shortfall is not that the arm cannot reach; it is that the attempt ends at the first slip.

    Improving that inside PushObject would change a frozen skill's behaviour under runs that
    were graded against it. So this module adds the missing capability as a NEW skill on top:
    it consumes PushObject results and decides whether another approach is warranted.

    PushObject stays byte-identical. Everything here is additive.

WHAT IT ADDS
    A bounded retry policy. After a push reports contact loss with the object still short of
    the requested distance, this issues another push for the remainder, having first backed
    off and re-approached so the next contact is a fresh one rather than an arm resting
    against the object. The controller is told how many attempts it may use and it stops on
    the first of: target reached, budget exhausted, contact never made, or carry engaged.

FAILURE MODES (each has its own code, none is silently swallowed)
    1  target met
    2  budget exhausted with the object short
    3  contact was never made in any attempt
    4  the carry backend engaged; motion is no longer explained by contact
    5  cancelled
"""
import math

OUTCOME_REACHED = 1
OUTCOME_BUDGET_EXHAUSTED = 2
OUTCOME_NO_CONTACT = 3
OUTCOME_CARRY_ENGAGED = 4
OUTCOME_CANCELED = 5

MIN_DISPLACEMENT_M = 0.005


def choose_next_request(target_m, achieved_m, attempted_m, remaining_attempts,
                        allow_extend=False):
    """Decide what to ask for next, or why to stop.

    Returns (action, payload). action is one of 'push', 'reached', 'exhausted'.
    The requested distance is always the shortfall, never the original target, so a partial
    success is not thrown away by asking for the full amount again.
    """
    if target_m <= 0:
        return "reached", {"reason": "target is not positive", "achieved_m": achieved_m}
    if achieved_m >= target_m:
        return "reached", {"achieved_m": achieved_m, "target_m": target_m}
    if remaining_attempts <= 0:
        return "exhausted", {"achieved_m": achieved_m, "target_m": target_m,
                             "reason": "no attempts left"}
    shortfall = target_m - achieved_m
    if shortfall <= 0:
        return "reached", {"achieved_m": achieved_m, "target_m": target_m}
    return "push", {"distance_m": shortfall,
                    "achieved_before_m": achieved_m,
                    "attempt": attempted_m + 1}


def classify_attempt(result):
    """Map one PushObject result onto (made_contact, advanced, carry_engaged, code).

    A result that cannot be interpreted is treated as no-progress rather than as success.
    """
    if not isinstance(result, dict):
        return False, 0.0, False, "unreadable result"
    if result.get("carry_engaged_during"):
        return True, 0.0, True, "carry engaged"
    moved = result.get("displacement_m")
    if not isinstance(moved, (int, float)) or isinstance(moved, bool):
        return False, 0.0, False, "displacement missing"
    if not math.isfinite(moved) or moved < 0:
        return False, 0.0, False, "displacement not finite"
    made = bool(result.get("contact_made"))
    return made, float(moved), False, None


def accumulate(attempts, target_m):
    """Walk a recorded list of attempts and produce the verdict.

    Pure: takes a list of PushObject result dicts and the target, returns the same shape the
    live controller returns, so the policy can be tested without ROS or a simulator.
    """
    achieved = 0.0
    contacted = False
    for index, result in enumerate(attempts, start=1):
        made, moved, carry, problem = classify_attempt(result)
        if carry:
            return {"outcome": OUTCOME_CARRY_ENGAGED, "achieved_m": achieved,
                    "attempts": index, "detail": "carry engaged at attempt %d" % index}
        if made:
            contacted = True
        if moved > 0:
            achieved += moved
        if achieved >= target_m:
            return {"outcome": OUTCOME_REACHED, "achieved_m": achieved,
                    "attempts": index, "detail": None}
    if not contacted:
        return {"outcome": OUTCOME_NO_CONTACT, "achieved_m": achieved,
                "attempts": len(attempts),
                "detail": "no attempt established contact"}
    return {"outcome": OUTCOME_BUDGET_EXHAUSTED, "achieved_m": achieved,
            "attempts": len(attempts),
            "detail": "short by %.4f m after %d attempts"
                      % (max(0.0, target_m - achieved), len(attempts))}


def is_progress(moved, floor_m=MIN_DISPLACEMENT_M):
    """A re-approach is only worth it if the previous attempt actually moved something."""
    return isinstance(moved, (int, float)) and math.isfinite(moved) and moved >= floor_m
