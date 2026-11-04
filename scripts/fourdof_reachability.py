#!/usr/bin/env python3
"""Read-only 4DOF release-attitude reachability check for issue #121.

The OpenMANIPULATOR-X arm group has four active revolute joints: joint1 about
Z, and joint2/3/4 all about *parallel* Y axes (verified from the upstream
URDF). Therefore the end-effector attitude is Rz(j1) * Ry(phi) with

    phi = j2 + j3 + j4

and there is no roll degree of freedom at all. A box rigidly carried by the
end effector inherits that pitch, so its tilt away from world Z is |phi|
(up to the fixed attach-frame offset). MoveIt's kinematics.yaml sets
``position_only_ik: True``, so the solver never constrains phi: for a given
EE position the planner takes whatever phi its seed produces.

This module answers the question issue #121 asks before allowing any fix:
for a given EE target, does the joint-limit-bounded IK null space contain a
phi close enough to zero for a stable (near-level) release?

Nothing here dispatches motion, changes the planner, or claims an acceptance
result. FK uses only the upstream URDF geometry; no simulator is started.

Usage:
  python3 scripts/fourdof_reachability.py --urdf /path/to/open_manipulator_x.urdf \
      --target 0.1118,-0.1398,0.1868 [--scan]
"""
from __future__ import annotations

import argparse
import json
import math
import xml.etree.ElementTree as ET

JOINT_NAMES = ("joint1", "joint2", "joint3", "joint4")
EE_JOINT = "end_effector_joint"
LIMITS = {
    "joint1": (-math.pi, math.pi),
    "joint2": (-1.5, 1.5),
    "joint3": (-1.5, 1.4),
    "joint4": (-1.7, 1.97),
}
POSITION_TOLERANCE_M = 0.001  # 1 mm: below this a solution "reaches" the target
LEVEL_TILT_DEG = 5.0  # what we would need for a stable release


def parse_chain(urdf_path):
    """Return [(origin_xyz, axis_xyz), ...] for joint1..4 and the fixed EE offset."""
    root = ET.parse(urdf_path).getroot()
    joints = {j.get("name"): j for j in root.findall("joint")}
    chain = []
    for name in JOINT_NAMES:
        j = joints[name]
        origin = j.find("origin")
        axis = j.find("axis")
        xyz = tuple(float(v) for v in origin.get("xyz").split())
        ax = tuple(float(v) for v in axis.get("xyz").split())
        chain.append((xyz, ax))
    ee = joints[EE_JOINT].find("origin")
    ee_offset = tuple(float(v) for v in ee.get("xyz").split())
    return chain, ee_offset


def identity():
    return [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]


def matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)]
            for i in range(4)]


def translation(xyz):
    t = identity()
    for i in range(3):
        t[i][3] = xyz[i]
    return t


def rotation(axis, angle):
    x, y, z = axis
    c, s, v = math.cos(angle), math.sin(angle), 1.0 - math.cos(angle)
    r = identity()
    r[0][0] = c + x * x * v
    r[0][1] = x * y * v - z * s
    r[0][2] = x * z * v + y * s
    r[1][0] = y * x * v + z * s
    r[1][1] = c + y * y * v
    r[1][2] = y * z * v - x * s
    r[2][0] = z * x * v - y * s
    r[2][1] = z * y * v + x * s
    r[2][2] = c + z * z * v
    return r


def fk(q, chain, ee_offset):
    t = identity()
    for (origin, axis), angle in zip(chain, q):
        t = matmul(t, matmul(translation(origin), rotation(axis, angle)))
    return matmul(t, translation(ee_offset))


def ee_position(q, chain, ee_offset):
    t = fk(q, chain, ee_offset)
    return (t[0][3], t[1][3], t[2][3])


def ee_up(q, chain, ee_offset):
    """End-effector local +Z in world; its tilt from world Z is |phi|."""
    t = fk(q, chain, ee_offset)
    return (t[0][2], t[1][2], t[2][2])


def pitch_deg(q):
    return math.degrees(q[1] + q[2] + q[3])


def joint_limits_ok(q):
    return all(LIMITS[n][0] - 1e-9 <= v <= LIMITS[n][1] + 1e-9
               for n, v in zip(JOINT_NAMES, q))


def residual(v, target, phi, chain, ee_offset):
    """Residual for least-squares: position error + soft limit penalties."""
    j1, j2, j3 = v
    j4 = phi - j2 - j3
    q = (j1, j2, j3, j4)
    p = ee_position(q, chain, ee_offset)
    out = [p[0] - target[0], p[1] - target[1], p[2] - target[2]]
    for name, value in zip(JOINT_NAMES, q):
        lo, hi = LIMITS[name]
        if value < lo:
            out.append((lo - value) * 10.0)
        elif value > hi:
            out.append((value - hi) * 10.0)
        else:
            out.append(0.0)
    return out


def solve_at_pitch(target, phi, chain, ee_offset, seeds=None):
    """Minimum position error achievable with a fixed end-effector pitch."""
    try:
        from scipy.optimize import least_squares
    except ImportError:
        raise RuntimeError("scipy is required for the reachability scan")
    best = None
    if seeds is None:
        seeds = [(a, b, c)
                 for a in (0.0, 0.8, -0.8)
                 for b in (-0.6, 0.0, 0.6)
                 for c in (-0.6, 0.0, 0.6)]
    for seed in seeds:
        fit = least_squares(residual, seed,
                            args=(target, phi, chain, ee_offset),
                            max_nfev=400, ftol=1e-12, xtol=1e-12, gtol=1e-12)
        j1, j2, j3 = fit.x
        q = (j1, j2, j3, phi - j2 - j3)
        p = ee_position(q, chain, ee_offset)
        err = math.dist(p, target)
        if best is None or err < best[0]:
            best = (err, q)
    return best


def scan(target, chain, ee_offset, step_deg=5.0, span_deg=90.0, tolerance=POSITION_TOLERANCE_M):
    rows = []
    n = int(span_deg / step_deg)
    for k in range(-n, n + 1):
        deg = k * step_deg
        phi = math.radians(deg)
        err, q = solve_at_pitch(target, phi, chain, ee_offset)
        rows.append({"pitch_deg": deg,
                     "position_error_mm": round(err * 1000.0, 4),
                     "reachable": err <= tolerance and joint_limits_ok(q),
                     "limits_ok": joint_limits_ok(q),
                     "joints_rad": [round(v, 5) for v in q]})
    reachable = [r["pitch_deg"] for r in rows if r["reachable"]]
    return {
        "target": list(target),
        "tolerance_mm": tolerance * 1000.0,
        "reachable_pitch_range_deg": [min(reachable), max(reachable)] if reachable else None,
        "level_release_possible": bool(reachable) and min(abs(v) for v in reachable) <= LEVEL_TILT_DEG,
        "closest_to_level_deg": min(reachable, key=abs) if reachable else None,
        "scan": rows,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--urdf", required=True)
    ap.add_argument("--target", required=True,
                    help="comma-separated EE xyz, e.g. 0.1118,-0.1398,0.1868")
    ap.add_argument("--scan", action="store_true", help="include the full pitch scan")
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    chain, ee_offset = parse_chain(args.urdf)
    target = tuple(float(v) for v in args.target.split(","))
    report = scan(target, chain, ee_offset)
    report["urdf"] = args.urdf
    report["chain"] = [{"origin": list(o), "axis": list(a)} for o, a in chain]
    report["ee_offset"] = list(ee_offset)
    report["model"] = "Rz(j1)*Ry(j2+j3+j4); no roll DOF; position_only_ik=True upstream"
    if not args.scan:
        report.pop("scan")
    text = json.dumps(report, indent=2)
    print(text)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
