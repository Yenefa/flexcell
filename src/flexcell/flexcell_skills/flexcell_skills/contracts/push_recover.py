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


def made_contact(result):
    return bool(result.get("contact_made"))


def classify_attempt(result):
    """Map one PushObject result onto (made_contact, advanced, carry_engaged, code).

    A result that cannot be interpreted is treated as no-progress rather than as success.
    """
    if not isinstance(result, dict):
        return False, 0.0, False, "unreadable result"
    if result.get("carry_engaged_during"):
        return True, 0.0, True, "carry engaged"
    # SIGNED displacement, not magnitude.
    #
    # A real run caught this: the policy used displacement_m, which is the unsigned
    # magnitude of the object's motion, so a block flicked BACKWARD counted as progress.
    # Three of five trials kept "recovering" while the block moved away from the target,
    # ending at x=0.29, 0.36 and 0.41 against a start of 0.22 and a target of roughly 0.13.
    # displacement_along_direction_m is the projection onto the commanded direction and
    # carries its sign, which is the only field that can answer "did it move toward the goal".
    moved = result.get("displacement_along_direction_m")
    if moved is None:
        moved = result.get("displacement_m")
    if not isinstance(moved, (int, float)) or isinstance(moved, bool):
        return False, 0.0, False, "displacement missing"
    if not math.isfinite(moved):
        return False, 0.0, False, "displacement not finite"
    if moved < 0:
        return made_contact(result), 0.0, False, "object moved backwards"
    made = bool(result.get("contact_made"))
    return made, float(moved), False, None


ERR_CONTACT_NOT_MADE = 27
ERR_CONTACT_LOST = 28

# Error codes whose reported displacement cannot be acted on.
#
# MEASURED, not assumed. Comparing the skill's own displacement_m against ground-truth
# travel on 29 archived T08 runs: every ec 36 ERR_DISPLACEMENT_OVERSHOOT run reported
# within a few millimetres of reality (ratios 1.00, 1.00, 1.02, 0.99, 0.98, 0.93), while
# ec 28 runs reported small positive displacements -x while the box ended up FURTHER IN +x
# than its start: 0.0079 reported against -0.0647 actual, 0.0481 against -0.0955, 0.0221
# against -0.1156, 0.0518 against -0.1486. Mean gap over all 29 runs: -0.0209 m.
#
# So for these two codes both the magnitude AND the sign are unreliable. A recovery policy
# that accumulates them is integrating a number that points the wrong way.
UNRELIABLE_DISPLACEMENT_CODES = frozenset((ERR_CONTACT_NOT_MADE, ERR_CONTACT_LOST))


def displacement_is_trustworthy(result):
    """False when the reported displacement must not be used for a policy decision.

    Callers should re-observe the object rather than accumulate the value. Returns
    True for anything not in UNRELIABLE_DISPLACEMENT_CODES, including results with no
    error_code at all, so this can only ever withhold a number, never invent one.
    """
    if not isinstance(result, dict):
        return False
    try:
        code = int(result.get("error_code"))
    except (TypeError, ValueError):
        return True
    return code not in UNRELIABLE_DISPLACEMENT_CODES


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