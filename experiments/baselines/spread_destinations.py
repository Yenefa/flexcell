#!/usr/bin/env python3
"""Assign physically distinct destinations when several stages share one bin.

WHY: a task can legitimately ask for two objects in the SAME bin (T03 "move blocks
into the right bin in this order"). Emitting the same bin CENTRE for both stages makes
the composite planner reject the second one with "declared destination occupied", so a
correct plan is graded as a failure. That is a task-materialisation defect, not an agent
failure and not a robot failure.

This module only spreads positions INSIDE the declared bin radius. It does not change
the evaluator, any tolerance, the acceptance radius, or the clearance contract.
The spread is derived from the plan itself (which the agent produced), never from the
expected_goal, so it cannot leak an answer.
"""
import math

# Separation between two objects placed in the SAME bin.
#
# HISTORY, because this number was wrong twice:
#   clearance contract        = 50 mm  (unchanged)
#   bin radius                = 60 mm  (unchanged)
#   0.056 was chosen to sit 6 mm above clearance and fit inside the radius.
#   MEASURED on the robot: boxes drift about 7-10 mm from their planned landing
#   point, so the effective gap fell to 0.049 m - BELOW clearance - and the composite
#   rejected the second stage with "declared destination occupied". Four T13 runs
#   failed this way for exactly this reason.
#
# 0.090 leaves 40 mm of margin over clearance, more than twice the observed drift, and
# +/-45 mm still fits inside the 60 mm bin radius. This WIDENS separation; it does not
# relax any threshold.
SPREAD_STEP_M = 0.090


def spread(stages, bin_radius=0.06, avoid=None, clearance=0.05):
    """Return a new stage list with distinct destinations for same-bin groups.

    `avoid` lists positions of other objects. Every produced destination must stay at
    least `clearance` away from each of them.

    WHY THE AVOIDANCE EXISTS, measured on the robot: T12 revisits zone_1 twice. Spreading
    along +x pushed the second landing spot to x=0.165, which is only 46 mm from box_b
    spawn at (0.20, -0.18) - BELOW the 50 mm clearance - so the composite rejected it
    with "declared destination occupied" and six runs failed identically. Spreading along
    one fixed axis is not enough; the axis has to be chosen so the offsets do not walk
    into another object.
    """
    own = [[float(a), float(b)] for a, b in (avoid or [])]
    groups = {}
    order = []
    for i, s in enumerate(stages):
        key = tuple(round(float(v), 5) for v in s["place_pose"])
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(i)

    def offsets(n):
        return [(r - (n - 1) / 2.0) * SPREAD_STEP_M for r in range(n)]

    def along(centre, offs, axis):
        pts = []
        for o in offs:
            pts.append([centre[0], centre[1] + o] if axis == 1
                       else [centre[0] + o, centre[1]])
        return pts

    def margin(pts):
        """Smallest distance from any produced point to any avoided object."""
        if not own:
            return float("inf")
        return min(math.hypot(px - ax, py - ay)
                   for px, py in pts for ax, ay in own)

    result = [dict(s, place_pose=list(s["place_pose"])) for s in stages]
    for key in order:
        idxs = groups[key]
        if len(idxs) < 2:
            continue
        centre = (key[0], key[1])
        offs = offsets(len(idxs))
        best_axis, best_pts = 0, along(centre, offs, 0)
        if own:
            for axis in (0, 1):
                pts = along(centre, offs, axis)
                if margin(pts) > margin(best_pts):
                    best_axis, best_pts = axis, pts
        for rank, i in enumerate(idxs):
            cand = list(best_pts[rank]) + [key[2]]
            if math.hypot(cand[0] - centre[0], cand[1] - centre[1]) > bin_radius:
                raise ValueError(
                    "cannot place %d objects in a %.3f m bin while keeping the "
                    "%.3f m separation the clearance contract needs"
                    % (len(idxs), bin_radius, SPREAD_STEP_M))
            if margin([best_pts[rank]]) < clearance:
                raise ValueError(
                    "no spread direction keeps every destination %.3f m clear of the "
                    "other objects; refusing rather than emitting a plan that will be "
                    "rejected on the robot" % clearance)
            result[i]["place_pose"] = cand
            result[i]["spread_offset_m"] = round(offs[rank], 5)
            result[i]["spread_axis"] = "y" if best_axis == 1 else "x"
    return result
