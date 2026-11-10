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

# Two 35 mm boxes need >= 50 mm centre separation under the plan clearance contract.
# +/-28 mm keeps both inside a 60 mm bin radius and 56 mm apart.
SPREAD_STEP_M = 0.056


def spread(stages, bin_radius=0.06):
    """Return a new stage list with distinct destinations for same-bin groups."""
    groups = {}
    order = []
    for i, s in enumerate(stages):
        key = tuple(round(float(v), 5) for v in s["place_pose"])
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(i)

    result = [dict(s, place_pose=list(s["place_pose"])) for s in stages]
    for key in order:
        idxs = groups[key]
        if len(idxs) < 2:
            continue
        centre = (key[0], key[1])
        for rank, i in enumerate(idxs):
            offset = (rank - (len(idxs) - 1) / 2.0) * SPREAD_STEP_M
            # Spread along x, which is the arm-forward axis in this cell.
            candidate = [centre[0] + offset, centre[1], key[2]]
            if math.hypot(candidate[0] - centre[0], candidate[1] - centre[1]) > bin_radius:
                raise ValueError("cannot fit %d objects inside a %.3f m bin"
                                 % (len(idxs), bin_radius))
            result[i]["place_pose"] = candidate
            result[i]["spread_offset_m"] = round(offset, 5)
    return result
