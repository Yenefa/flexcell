"""Verdict for the PLACE release aperture: did the jaws actually open?

Deliberately free of ROS imports: this decision has to be testable without a
graph, a simulator or a physical window.

WHAT WAS WRONG (measured, docs/MISSION_UPDATE_20261112_R5.md 19.2): the release
was judged against the COMMANDED open position (0.02 m). This gripper reaches
0.0104 m in free space, so the aperture error at full open is 0.0096 m - almost
twice the 0.005 m tolerance. The check passed only while the controller also
reported reached_goal, so one stalled flag turned a release that physically
happened into a false PLACE failure (51 of 539 place attempts over the project
history, false negatives, not false successes).

WHAT THIS DOES: the reachable aperture is a calibration fact, so it is a
parameter (gripper_open_reference_m); 0.0 means "not calibrated". The tolerance
is unchanged and the check is neither skipped nor relaxed - two independent
conditions must hold: the jaws moved off the closed end, and the achieved
aperture is within the same tolerance of the reachable reference.

CALIBRATED (reference > 0) - the fixed regime. The measurement decides, so
reached_goal never has to save the release and can never rescue a measured
shortfall. A replay of the 117 place rows recorded in this repository's runs
shows what that changes: 103 releases measured 0.01027-0.01076 m and passed
only because reached_goal was also set; measured against 0.0104 m they pass on
the aperture itself.

UNCALIBRATED (reference = 0) - the pre-fix regime, kept on purpose. Comparing a
reachable 0.0104 m against the commanded 0.02 m is the defect, so without a
calibrated reference there is no honest way to judge the measurement; dropping
the old reached_goal acceptance there would fail all 103 of those releases
instead of fixing the one defect, which is a false-failure generator, not a
fix. The uncalibrated branch therefore accepts a reached_goal claim exactly as
before, says so in its detail and in reason == 'reached_goal_uncalibrated', and
disappears as soon as the reference is calibrated.
"""
import math

# 0.0 means "not calibrated": the pre-fix comparison against the command, with
# the pre-fix acceptance, is kept for such a robot (see the module docstring).
DEFAULT_OPEN_REFERENCE_M = 0.0
DEFAULT_TOLERANCE_M = 0.005
# Closed end of the prismatic gripper joint in metres - the same quantity
# pick_server declares as gripper_close_position. Used only to tell "the jaws
# moved" from "the jaws never moved", never as an aperture target.
DEFAULT_CLOSED_POSITION_M = -0.011

# Failures keep this prefix: runtime/recovery/execution_root_cause.py (STALL_OPEN)
# and evolution/proposals/generate.py bucket place failures by this substring, so
# records written before and after the fix stay comparable.
FAILURE_PREFIX = 'gripper did not open'


def _as_float(value):
    """float(value), or None for anything that cannot be a measurement."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _finite(value):
    return value is not None and math.isfinite(value)


def effective_open_reference_m(requested_m, reference_m=None):
    """The aperture the release is measured against.

    A positive, finite reference_m is the calibrated free-space reach. 0.0, a
    negative value or a non-finite one mean "not calibrated": fall back to the
    commanded position, which is exactly the pre-fix comparison.
    """
    requested = _as_float(requested_m)
    reference = _as_float(reference_m)
    if _finite(reference) and reference > 0.0:
        return reference
    return requested


def release_aperture_verdict(open_state, requested_m, reference_m=None,
                             closed_m=DEFAULT_CLOSED_POSITION_M,
                             tolerance_m=DEFAULT_TOLERANCE_M):
    """Decide whether one release aperture confirms the carry was released.

    open_state is the dict from common.gripper_outcome(). A state without the
    controller flags is accepted on purpose: the verdict must rest on the
    measurement, not on a key being present.

    Returns a dict:
      ok           - True when the release aperture is confirmed, or when the
                     controller reported no aperture at all (silence is not a
                     failed release; the physical drop check still decides)
      reason       - reached / reached_goal_uncalibrated / short_of_reference /
                     no_motion / nonfinite / unmeasured / invalid_limit
      detail       - the sentence the skill logs. Failures keep FAILURE_PREFIX
                     and always name requested, reference, position and stalled,
                     so the defect stays traceable from a run log alone.
      requested_m, reference_m, calibrated, closed_m, tolerance_m, position_m,
      stalled, reached_goal - the inputs the decision used, for the JSONL record.
    """
    state = open_state if isinstance(open_state, dict) else {}
    position = _as_float(state.get("position"))
    stalled = state.get("stalled")
    reached_goal = bool(state.get("reached_goal", False))
    requested = _as_float(requested_m)
    raw_reference = _as_float(reference_m)
    reference = effective_open_reference_m(requested, reference_m)
    closed = _as_float(closed_m)
    tolerance = _as_float(tolerance_m)

    verdict = {
        "ok": False,
        "reason": "",
        "detail": "",
        "requested_m": requested,
        "reference_m": reference,
        "calibrated": _finite(raw_reference) and raw_reference > 0.0,
        "closed_m": closed,
        "tolerance_m": tolerance,
        "position_m": position,
        "stalled": stalled,
        "reached_goal": reached_goal,
    }

    if not _finite(tolerance) or tolerance < 0.0:
        # Failing open on a broken tolerance would be a silent pass.
        verdict["reason"] = 'invalid_limit'
        verdict["detail"] = (
            'release aperture check unusable (tolerance=%r requested=%r '
            'reference=%r position=%r)' % (tolerance_m, requested, reference, position))
        return verdict
    if not _finite(reference):
        verdict["reason"] = 'invalid_limit'
        verdict["detail"] = (
            'release aperture check unusable (requested=%r reference=%r)'
            % (requested_m, reference_m))
        return verdict

    if position is None:
        # The controller reported neither an aperture nor usable flags. That is
        # not evidence of a failed release: keep the pre-fix contract and let
        # the drop check decide, instead of inventing a failure.
        verdict["ok"] = True
        verdict["reason"] = 'unmeasured'
        verdict["detail"] = (
            'release aperture unmeasured (position=%r requested=%r reference=%r '
            'stalled=%r reached_goal=%r): the controller reported no aperture, so '
            'the drop check decides the physical outcome'
            % (position, requested, reference, stalled, reached_goal))
        return verdict

    # reference is finite here, so this is safe even for a NaN/inf measurement.
    error = abs(position - reference)
    if not _finite(position):
        verdict["reason"] = 'nonfinite'
        verdict["detail"] = (
            FAILURE_PREFIX + ' (position=%r requested=%r reference=%r stalled=%r '
            'reached_goal=%r error=%r tolerance=%r): the measured aperture is not a '
            'finite number, so the release is unverified'
            % (position, requested, reference, stalled, reached_goal, error,
               tolerance))
        return verdict

    closed_offset = None if not _finite(closed) else abs(position - closed)

    if closed_offset is not None and closed_offset <= tolerance:
        verdict["reason"] = 'no_motion'
        verdict["detail"] = (
            FAILURE_PREFIX + ' (position=%r requested=%r reference=%r stalled=%r '
            'reached_goal=%r error=%.4f closed_offset=%.4f tolerance=%.4f): the jaws '
            'never left the closed position %r, so the release is unconfirmed'
            % (position, requested, reference, stalled, reached_goal, error,
               closed_offset, tolerance, closed))
        return verdict

    if error > tolerance:
        compared_to = ('reachable open reference' if verdict["calibrated"]
                       else 'commanded open, because gripper_open_reference_m is '
                            'uncalibrated (0.0)')
        if not verdict["calibrated"] and reached_goal:
            # Nothing calibrated to measure against and the command is
            # unreachable on this gripper, so the controller claim is the only
            # evidence there is. Keep the pre-fix acceptance rather than turn
            # every release on an uncalibrated robot into a false failure; the
            # reason and the detail make the weaker basis explicit.
            verdict["ok"] = True
            verdict["reason"] = 'reached_goal_uncalibrated'
            verdict["detail"] = (
                'release aperture accepted without a calibrated reference '
                '(position=%r requested=%r reference=%r stalled=%r reached_goal=%r '
                'error=%.4f tolerance=%.4f): the controller reported the goal was '
                'reached and gripper_open_reference_m is uncalibrated (0.0), so the '
                'measured reach cannot decide; calibrate the reachable aperture to '
                'judge this on the measurement'
                % (position, requested, reference, stalled, reached_goal, error,
                   tolerance))
            return verdict
        verdict["reason"] = 'short_of_reference'
        verdict["detail"] = (
            FAILURE_PREFIX + ' (position=%r requested=%r reference=%r stalled=%r '
            'reached_goal=%r error=%.4f tolerance=%.4f): the achieved aperture is '
            '%.4f m from the %s'
            % (position, requested, reference, stalled, reached_goal, error,
               tolerance, error, compared_to))
        return verdict

    verdict["ok"] = True
    verdict["reason"] = 'reached'
    verdict["detail"] = (
        'release aperture confirmed (position=%r requested=%r reference=%r '
        'stalled=%r reached_goal=%r error=%.4f tolerance=%.4f)'
        % (position, requested, reference, stalled, reached_goal, error, tolerance))
    return verdict
