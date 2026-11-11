#!/usr/bin/env python3
"""A claim check that is allowed to say "achieved" only when it cannot be wrong both ways.

WHY NOT THE OBVIOUS VERSION: the previous check compared measured positions against the plan's
targets using the plan's own tolerance (20 mm). Measured plans place targets 45 mm from a zone
centre with a 60 mm radius, so 15 mm of slack, and 20 mm of tolerance lets an object sit outside
the zone while the check still says satisfied. That is a false success produced by a CORRECT plan.

TWO CONDITIONS INSTEAD OF ONE:
  1. the object is within the plan's tolerance of where the plan said to put it  (execution)
  2. the object is inside the radius of the zone that plan stage aims at         (acceptance)
Both are derived from data the agent can see: its own plan, its own measurement, and the zone
radius in its observation. Neither reads the sealed answer.

STILL REFUSES WHERE IT CANNOT TELL: if the same object appears in more than one plan stage, the
goal includes an ordering that positions cannot prove, so it returns None rather than guessing.
A None is not a failure - it means "ask something else".
"""
import json
import math


def _dist2(a, b):
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _nearest_zone(pose, zones):
    best = None
    for z in zones:
        c = z.get("position")
        if not c:
            continue
        d = _dist2(pose, c)
        if best is None or d < best[0]:
            best = (d, z)
    return best[1] if best else None


def check(plan, measured, zones):
    """Return (verdict, detail) where verdict is True, False, or None (cannot tell)."""
    stages = plan.get("stages") or []
    if not stages:
        return None, {"why": "plan has no stages"}
    counts = {}
    for st in stages:
        n = st.get("object_name")
        counts[n] = counts.get(n, 0) + 1
    repeated = sorted(n for n, c in counts.items() if c > 1)
    if repeated:
        return None, {"why": "an object appears in more than one stage, so the goal includes "
                             "an ordering positions cannot prove",
                      "repeated_objects": repeated}
    tol = plan.get("position_tolerance_m")
    if tol is None:
        return None, {"why": "plan declares no position_tolerance_m"}
    tol = float(tol)
    measured = measured or {}
    rows = []
    all_ok = True
    missing = 0
    for st in stages:
        name = st.get("object_name")
        target = st.get("place_pose")
        pose = measured.get(name)
        if pose is None or target is None:
            missing += 1
            rows.append({"stage": st.get("stage_id"), "object": name,
                         "status": "NOT_MEASURED"})
            all_ok = False
            continue
        zone = _nearest_zone(target, zones)
        d_target = _dist2(pose, target)
        within_plan = d_target <= tol
        inside_zone = False
        d_centre = None
        radius = None
        if zone is not None and zone.get("position"):
            d_centre = _dist2(pose, zone["position"])
            radius = float(zone.get("radius", 0.0))
            inside_zone = d_centre <= radius
        ok = within_plan and inside_zone
        if not ok:
            all_ok = False
        rows.append({
            "stage": st.get("stage_id"), "object": name,
            "distance_to_plan_m": round(d_target, 5),
            "plan_tolerance_m": tol,
            "within_plan": within_plan,
            "zone": zone.get("name") if zone else None,
            "distance_to_zone_centre_m": None if d_centre is None else round(d_centre, 5),
            "zone_radius_m": radius,
            "inside_zone": inside_zone,
            "ok": ok,
        })
    if missing:
        return None, {"why": "an object was not measured", "stages": rows}
    return all_ok, {"stages": rows,
                    "why": ("both conditions met for every stage" if all_ok else
                            "at least one stage fails execution or acceptance")}
