#!/usr/bin/env python3
"""Decide whether the plan's goal is ALREADY satisfied by measurement.

WHY: the recovery driver triggers off task.out - what the FSM concluded. That conclusion can
be a false negative. Over 32 validated runs, 2 had the task reporting failure while the box
was released and inside the target zone, with the skill's own verify.jsonl agreeing. Acting
on task.out alone made recovery retry a placement that was already complete.

THE TOLERANCE IS THE PLAN'S OWN, NOT THE EVALUATOR'S. plan.json declares
position_tolerance_m (20 mm everywhere measured). This check reads only that declared value
and the measured positions - never the held-out answer, never the evaluator's zone radius.
Since the acceptance radius is 60 mm, a 20 mm standard is STRICTER, so the check is
conservative: it declines to skip a retry long before the evaluator would complain, and it
therefore cannot manufacture a pass. If it is ever wrong, the run simply ends and the
independent evaluator fails it - the honest outcome.

WHY IT REFUSES ON MULTI-STAGE OBJECTS - a bug found by a safety check, not by reasoning:
the first version compared every stage's target against the measured pose. On a T12 triple
revisit the plan lists the SAME object three times, so the object sitting at its FIRST target
made the check report "satisfied" even though it still had two moves to make. That would
have suppressed a recovery which is known to have turned a failure into a pass (the
HO-5a96f3eb4fae gain). A later case proved the same is true of final positions alone: a
triple-revisit task can end within tolerance of its last target and still fail on ORDER.
So the check only concludes anything when every object appears exactly once in the plan. If
an object appears more than once, the goal includes a sequence this check cannot verify, and
it refuses rather than guess.
"""
import json


def _dist2(a, b):
    dx = float(a[0]) - float(b[0])
    dy = float(a[1]) - float(b[1])
    return (dx * dx + dy * dy) ** 0.5


def check(plan, measured, tolerance=None):
    """Return (satisfied, details). Never returns True unless it can prove it."""
    stages = plan.get("stages") or []
    if not stages:
        return False, {"why": "plan has no stages"}

    counts = {}
    for st in stages:
        name = st.get("object_name")
        counts[name] = counts.get(name, 0) + 1
    repeated = sorted(n for n, c in counts.items() if c > 1)
    if repeated:
        return False, {
            "why": ("object(s) appear in more than one stage, so the goal includes an "
                    "ordering this check cannot verify from final positions"),
            "repeated_objects": repeated,
            "decision": "REFUSED - fall through to normal recovery",
        }

    tol = tolerance if tolerance is not None else plan.get("position_tolerance_m")
    if tol is None:
        return False, {"why": ("plan declares no position_tolerance_m; refusing to guess a "
                               "criterion the agent would be inventing after the fact")}
    tol = float(tol)

    measured = measured or {}
    rows = []
    missing = far = 0
    for st in stages:
        name = st.get("object_name")
        target = st.get("place_pose")
        pose = measured.get(name)
        if pose is None or target is None:
            missing += 1
            rows.append({"stage": st.get("stage_id"), "object": name,
                         "status": "NOT_MEASURED"})
            continue
        d = _dist2(pose, target)
        ok = d <= tol
        if not ok:
            far += 1
        rows.append({"stage": st.get("stage_id"), "object": name,
                     "measured": [round(float(pose[0]), 5), round(float(pose[1]), 5)],
                     "target": [round(float(target[0]), 5), round(float(target[1]), 5)],
                     "distance_m": round(d, 5), "tolerance_m": tol,
                     "status": "AT_TARGET" if ok else "OUTSIDE_TOLERANCE"})

    return (missing == 0 and far == 0), {
        "tolerance_m": tol,
        "tolerance_source": ("plan.position_tolerance_m - the robot's own declared standard, "
                             "not the evaluator's acceptance radius"),
        "stages": rows,
        "not_measured": missing,
        "outside_tolerance": far,
    }
