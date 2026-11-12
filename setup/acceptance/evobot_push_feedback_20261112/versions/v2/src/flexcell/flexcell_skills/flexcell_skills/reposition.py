"""Opt-in measured lift/transfer/lower adapter; not a task verdict or planner.

Endpoint clearance bounds the tool envelope at those endpoints. A joint-space
trajectory can dip between them; only recorded simulation can test that path.
"""
import math


class RepositionCanceled(Exception):
    pass


class RepositionFailed(Exception):
    pass


def _position(value):
    if len(value) != 3 or not all(math.isfinite(float(v)) for v in value):
        raise RepositionFailed('missing or nonfinite position')
    return [float(v) for v in value]


def execute_reposition(target, *, read_pose, move, canceled, emit,
                       minimum_height_m, tracking_margin_m, carry_state,
                       stop_at_clearance=False):
    """Return the last motion tuple; refuse every unsafe/unknown intermediate step.

    read_pose returns (fresh measured xyz, error); it must check source age.
    move returns (ok, measured reach error, detail) and owns cancel/stop handling.
    No command is sent after an unsuccessful waypoint or unconfirmed clearance.
    """
    target = _position(target)
    if (not math.isfinite(minimum_height_m) or minimum_height_m <= 0
            or not math.isfinite(tracking_margin_m) or tracking_margin_m < 0):
        raise RepositionFailed('invalid declared clearance or tracking margin')

    def check_cancel():
        if canceled():
            raise RepositionCanceled('reposition canceled; no further waypoint dispatched')

    def measure():
        check_cancel()
        pose, error = read_pose()
        if error or pose is None:
            raise RepositionFailed('EE measurement unavailable: %s' % error)
        return _position(pose)

    start = measure()
    height = max(start[2], target[2], minimum_height_m + tracking_margin_m)
    waypoints = [('LIFT', [start[0], start[1], height]),
                 ('TRANSFER', [target[0], target[1], height])]
    if not stop_at_clearance:
        waypoints.append(('LOWER', target))
    emit('REPOSITION_PLAN', start=start, target=target, transit_z_m=height,
         minimum_measured_z_m=minimum_height_m)
    result = None
    for stage, waypoint in waypoints:
        actual_before = measure()
        if stage == 'TRANSFER' and actual_before[2] < minimum_height_m:
            raise RepositionFailed('measured lift below clearance; lateral transit refused')
        engaged, reason = carry_state()
        if engaged is not False:
            raise RepositionFailed('carry not confirmed disengaged: %s' % reason)
        check_cancel()
        emit('REPOSITION_WAYPOINT_REQUEST', stage=stage, target=waypoint,
             actual_before=actual_before)
        result = move(waypoint)
        check_cancel()
        ok, reach_error, detail = result
        if not ok:
            emit('REPOSITION_WAYPOINT_FAILED', stage=stage, reach_error_m=reach_error,
                 detail=detail)
            raise RepositionFailed('%s failed: %s' % (stage, detail))
        actual_after = measure()
        emit('REPOSITION_WAYPOINT_RESULT', stage=stage, actual_after=actual_after,
             reach_error_m=reach_error, detail=detail)
        if stage in ('LIFT', 'TRANSFER') and actual_after[2] < minimum_height_m:
            raise RepositionFailed('%s endpoint below measured clearance' % stage)
    if stop_at_clearance:
        error = math.dist(actual_after, target)
        reached = error <= tracking_margin_m
        emit('REPOSITION_HIGH_HOLD', actual_final=actual_after,
             requested_original_target=target, original_target_reached=reached,
             original_target_error_m=error)
        return reached, error, 'intentional high hold; original target reach is reported separately'
    return result
