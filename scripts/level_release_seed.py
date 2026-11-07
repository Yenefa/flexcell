#!/usr/bin/env python3
"""Compute a level-release IK seed for the attached-point PLACE path (#121).

The private planner in ``flexcell_mtc`` adds a fixed tip
``flexcell_attached_point`` at the measured box shape offset from
``end_effector_link`` and solves its *position* with position-only KDL. The
four active joints leave one redundant degree of freedom, which is the
end-effector pitch ``phi = j2+j3+j4`` (joint2/3/4 all rotate about parallel
Y). The solver never constrains phi, so the box can be released tilted.

This module does NOT change the planner. It computes, offline, the joint
vector that hits the same attached-point target with a chosen phi (default
0 = level release), verifies joint limits and reports the position error.
That vector is the concrete input a future planner-side seed/constraint
would need; emitting it here keeps the claim reproducible without a
simulator.

FK uses the real upstream URDF geometry via fourdof_reachability.py.

Usage:
  python3 scripts/level_release_seed.py --urdf <open_manipulator_x.urdf> \
      --box-target 0.12,-0.15,0.0295 [--phi 0] [--compare 6.7] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import math

import fourdof_reachability as fk
import release_drift_analysis as rda

# EE position minus box center, from recorded descend executor_target/target
# pairs (e.g. run104: EE (0.11176,-0.13979,0.18679), box (0.12,-0.15,0.0295)).
# The small x/y terms come from the attached shape frame; treat as an
# approximation, not an exact planner identity.
DEFAULT_BOX_OFFSET = (0.00824, -0.01021, -0.15729)  # box center relative to EE


def attached_point_position(q, chain, ee_offset, box_offset):
    """World position of the box centre carried at a fixed EE-frame offset."""
    t = fk.fk(q, chain, ee_offset)
    p = (t[0][3], t[1][3], t[2][3])
    return tuple(p[i] + sum(t[i][k] * box_offset[k] for k in range(3))
                 for i in range(3))


def residual(v, box_target, phi, chain, ee_offset, box_offset):
    j1, j2, j3 = v
    q = (j1, j2, j3, phi - j2 - j3)
    p = attached_point_position(q, chain, ee_offset, box_offset)
    out = [p[0] - box_target[0], p[1] - box_target[1], p[2] - box_target[2]]
    for name, value in zip(fk.JOINT_NAMES, q):
        lo, hi = fk.LIMITS[name]
        out.append(10.0 * (lo - value) if value < lo else
                   10.0 * (value - hi) if value > hi else 0.0)
    return out


def solve_level(target, phi_deg, chain, ee_offset, box_offset):
    """Best joint vector at a fixed phi; returns (error_m, q, limits_ok)."""
    try:
        from scipy.optimize import least_squares
    except ImportError:
        raise RuntimeError("scipy is required for the IK seed computation")
    phi = math.radians(phi_deg)
    best = None
    for s1 in (0.0, 0.9, -0.9, 1.8, -1.8):
        for s2 in (-0.7, 0.0, 0.7):
            for s3 in (-0.7, 0.0, 0.7):
                fit = least_squares(residual, (s1, s2, s3),
                                    args=(target, phi, chain, ee_offset, box_offset),
                                    max_nfev=500, ftol=1e-13, xtol=1e-13, gtol=1e-13)
                j1, j2, j3 = fit.x
                q = (j1, j2, j3, phi - j2 - j3)
                err = math.dist(attached_point_position(q, chain, ee_offset, box_offset),
                                target)
                if best is None or err < best[0]:
                    best = (err, q)
    err, q = best
    return err, q, fk.joint_limits_ok(q)


def report(target, chain, ee_offset, box_offset, phi, compare):
    out = {
        "box_target": list(target),
        "box_offset_ee_frame": list(box_offset),
        "note": "offset extrapolated from recorded executor_target/target pairs; not an exact planner identity",
        "solutions": [],
    }
    for deg in [phi] + ([] if compare is None else [compare]):
        err, q, ok = solve_level(target, deg, chain, ee_offset, box_offset)
        up = fk.ee_up(q, chain, ee_offset)
        tilt = math.degrees(math.acos(max(-1.0, min(1.0, up[2]))))
        out["solutions"].append({
            "phi_deg": deg,
            "position_error_mm": round(err * 1000.0, 5),
            "limits_ok": ok,
            "box_centre_from_fk": [round(v, 6) for v in
                                   attached_point_position(q, chain, ee_offset, box_offset)],
            "joints_rad": [round(v, 6) for v in q],
            "joints_deg": [round(math.degrees(v), 3) for v in q],
            "ee_up": [round(v, 6) for v in up],
            "ee_up_tilt_deg": round(tilt, 4),
            "geometric_predicted_shift_mm": round(rda.geometric_shift_mm(tilt), 4),
        })
    level, current = out["solutions"][0], (out["solutions"][1] if len(out["solutions"]) > 1 else None)
    out["level_seed_usable"] = bool(level["position_error_mm"] <= 1.0 and level["limits_ok"])
    if current is not None:
        out["predicted_shift_reduction_mm"] = round(
            current["geometric_predicted_shift_mm"] - level["geometric_predicted_shift_mm"], 4)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--urdf", required=True)
    ap.add_argument("--box-target", required=True, help="comma-separated box centre xyz")
    ap.add_argument("--box-offset", default=None,
                    help="comma-separated box centre offset in EE frame (default: recorded approx)")
    ap.add_argument("--phi", type=float, default=0.0, help="target pitch in degrees")
    ap.add_argument("--compare", type=float, default=None,
                    help="also solve at this pitch (e.g. the recorded tilt) for comparison")
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    chain, ee_offset = fk.parse_chain(args.urdf)
    target = tuple(float(v) for v in args.box_target.split(","))
    box_offset = (tuple(float(v) for v in args.box_offset.split(","))
                  if args.box_offset else DEFAULT_BOX_OFFSET)
    result = report(target, chain, ee_offset, box_offset, args.phi, args.compare)
    result["urdf"] = args.urdf
    text = json.dumps(result, indent=2)
    print(text)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
