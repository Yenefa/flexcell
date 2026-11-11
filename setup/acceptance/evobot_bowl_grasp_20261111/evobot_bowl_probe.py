#!/usr/bin/env python3
"""Measured diagnosis: why does NO bowl lift in libero_spatial?

A probe, not the controller. It measures the object's real geometry, its real collision
representation, the gripper's real opening, the real contact set and the real lift.
It never edits the benchmark, the environment, the retry controller or the side controller.

Sub-commands
  census   geometry + gripper + table census at the init pose AND at the settled pose,
           plus the retry controller's grasp-z arithmetic applied to both
  settle   what the object does under gravity from the pose set_init_state() installs
  trials   controlled grasp attempts at measured poses: pad gap, contacts, object lift
"""
import argparse
import json
import math
import os
import re
import sys
import time

ROOT = "/mnt/c/Users/fuker/Desktop/workspace/ext-bench/LIBERO"
SUITE = "libero_spatial"        # overridden by --suite
sys.path.insert(0, ROOT)

K_POS = 18.0
GRIP_OPEN = -1.0
GRIP_CLOSE = 1.0
LIFT_PROOF_M = 0.03
FRAC = 0.5            # the retry controller's GRASP_FRAC default
STANDOFF = 0.11       # the retry controller's STANDOFF
SETTLE_STEPS = 60     # the bowl is at rest after 20 steps (measured, see settle mode)


# ---------------------------------------------------------------- suite plumbing
def task_names():
    import importlib.util
    p = os.path.join(ROOT, "libero", "libero", "benchmark", "libero_suite_task_map.py")
    spec = importlib.util.spec_from_file_location("tm", p)
    tm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tm)
    return tm.libero_task_map[SUITE]


def task_files(idx):
    name = task_names()[idx]
    bddl = os.path.join(ROOT, "libero", "libero", "bddl_files", SUITE, name + ".bddl")
    init = os.path.join(ROOT, "libero", "libero", "init_files", SUITE, name + ".pruned_init")
    return name, bddl, init


def parse_goal(text):
    start = text.find("(:goal")
    pairs = re.findall(r"\((?:On|In)\s+([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\)", text[start:])
    keep = [(o, r) for o, r in pairs if r.endswith("_region")]
    return keep or pairs


def quat2mat(q):
    w, x, y, z = [float(v) for v in q]
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]]


def transpose3(R):
    return [[R[j][i] for j in range(3)] for i in range(3)]


def matvec(R, p):
    return [sum(R[i][j] * p[j] for j in range(3)) for i in range(3)]


def make_env(bddl):
    from libero.libero.envs import OffScreenRenderEnv
    env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=64, camera_widths=64)
    env.reset()
    return env


def load_init(init_path):
    import numpy as np
    import torch
    st = torch.load(init_path, map_location="cpu", weights_only=False)
    st = st.detach().cpu().numpy() if hasattr(st, "detach") else np.asarray(st)
    return np.asarray(st[0], dtype=float)


# ---------------------------------------------------------------- measurement helpers
def body_index(sim, name):
    return list(sim.model.body_names).index(name)


def find_obj_body(sim, obj):
    bodies = list(sim.model.body_names)
    if obj + "_main" in bodies:
        return obj + "_main"
    for b in bodies:
        if b.startswith(obj):
            return b
    return None


def geom_ids(sim, bid):
    return [g for g in range(sim.model.ngeom) if int(sim.model.geom_bodyid[g]) == bid]


def geom_world_verts(sim, g):
    """World-frame vertices of a mesh geom, or None if the geom is not a mesh."""
    m = sim.model
    if int(m.geom_type[g]) != 7:          # mjGEOM_MESH
        return None
    mid = int(m.geom_dataid[g])
    adr, num = int(m.mesh_vertadr[mid]), int(m.mesh_vertnum[mid])
    v = m.mesh_vert[adr:adr + num].astype(float)
    if hasattr(m, "mesh_pos"):
        Rm = quat2mat(m.mesh_quat[mid])
        mp = [float(x) for x in m.mesh_pos[mid]]
        v = v @ transpose3(Rm) + mp
    R = [list(row) for row in sim.data.geom_xmat[g].reshape(3, 3)]
    c = [float(x) for x in sim.data.geom_xpos[g]]
    return v @ transpose3(R) + c


def box_world_corners(sim, g):
    m = sim.model
    if int(m.geom_type[g]) != 6:          # mjGEOM_BOX
        return None
    h = [float(x) for x in m.geom_size[g]]
    R = [list(row) for row in sim.data.geom_xmat[g].reshape(3, 3)]
    c = [float(x) for x in sim.data.geom_xpos[g]]
    out = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                p = [sx * h[0], sy * h[1], sz * h[2]]
                d = matvec(R, p)
                out.append([c[i] + d[i] for i in range(3)])
    return out


def point_box_xy_distance(px, py, corners_xy):
    """Distance in xy from a point to a convex polygon (0 if inside). Corners: list of (x, y)."""
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    pts = sorted(set(corners_xy))
    if len(pts) < 3:
        return min(math.hypot(px - c[0], py - c[1]) for c in pts)
    lower, upper = [], []
    for pt in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], pt) <= 0:
            lower.pop()
        lower.append(pt)
    for pt in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], pt) <= 0:
            upper.pop()
        upper.append(pt)
    hull = lower[:-1] + upper[:-1]
    inside = True
    for i in range(len(hull)):
        a, b = hull[i], hull[(i + 1) % len(hull)]
        if cross(a, b, (px, py)) < 0:
            inside = False
            break
    if inside:
        return 0.0
    best = float("inf")
    for i in range(len(hull)):
        a, b = hull[i], hull[(i + 1) % len(hull)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - a[0]) * dx + (py - a[1]) * dy) / L2))
        best = min(best, math.hypot(px - (a[0] + t * dx), py - (a[1] + t * dy)))
    return best


def table_top_z(sim):
    names = list(sim.model.body_names)
    best = None
    for g in range(sim.model.ngeom):
        if "table" not in names[int(sim.model.geom_bodyid[g])].lower():
            continue
        cs = box_world_corners(sim, g)
        if cs:
            z = max(c[2] for c in cs)
            best = z if best is None else max(best, z)
    return best


def finger_joints(sim):
    out = []
    jn = list(sim.model.joint_names) if hasattr(sim.model, "joint_names") else []
    for j in range(sim.model.njnt):
        n = jn[j] if j < len(jn) else ""
        if "finger" in n:
            out.append({"name": n, "jid": j,
                        "qposadr": int(sim.model.jnt_qposadr[j]),
                        "range": [float(x) for x in sim.model.jnt_range[j]]})
    return out


def finger_bodies(sim):
    return [i for i, n in enumerate(sim.model.body_names) if "finger" in n]


def closing_axis(sim):
    fb = finger_bodies(sim)
    if len(fb) < 2:
        return None
    p = [sim.data.body_xpos[i] for i in fb[:2]]
    d = [float(p[1][0] - p[0][0]), float(p[1][1] - p[0][1])]
    n = math.hypot(*d)
    return None if n < 1e-9 else [d[0] / n, d[1] / n, 0.0]


def pad_geometry(sim):
    """Where are the finger pads relative to the grip site, and how far apart can they get?"""
    site = sim.model.site_name2id("gripper0_grip_site")
    eef = [float(x) for x in sim.data.site_xpos[site]]
    fb = finger_bodies(sim)
    axis = closing_axis(sim)
    boxes = []
    for b in fb:
        for g in range(sim.model.ngeom):
            if int(sim.model.geom_bodyid[g]) != b:
                continue
            cs = box_world_corners(sim, g)
            if not cs:
                continue
            boxes.append({"body": b, "geom": g,
                          "size": [round(float(x), 5) for x in sim.model.geom_size[g]],
                          "z": [min(c[2] for c in cs), max(c[2] for c in cs)],
                          "proj": [sum((c[i] - eef[i]) * axis[i] for i in range(3)) for c in cs]})
    if not boxes:
        return None
    z_lo = min(b["z"][0] for b in boxes)
    z_hi = max(b["z"][1] for b in boxes)
    # inner-face gap: negative-projection pad's max vs positive pad's min, along the jaw axis
    neg = [p for b in boxes for p in b["proj"] if p <= 0]
    pos = [p for b in boxes for p in b["proj"] if p > 0]
    gap = (min(pos) - max(neg)) if (neg and pos) else None
    return {"pad_z_range_world": [round(z_lo, 5), round(z_hi, 5)],
            "pad_z_offset_from_eef": [round(z_lo - eef[2], 5), round(z_hi - eef[2], 5)],
            "pad_half_height": round(0.5 * (z_hi - z_lo), 5),
            "pad_gap_m": round(gap, 5) if gap is not None else None,
            "n_geoms": len(boxes)}


def visual_geometry(sim, bid, centre):
    """Vertex-derived geometry of the VISUAL mesh geoms (which carry contype=0: not physical)."""
    import numpy as np
    m = sim.model
    verts = []
    for g in geom_ids(sim, bid):
        wv = geom_world_verts(sim, g)
        if wv is not None:
            verts.append(wv)
    if not verts:
        return {"vertex_derived": False}
    V = np.vstack(verts)
    cx, cy = float(centre[0]), float(centre[1])
    r = np.hypot(V[:, 0] - cx, V[:, 1] - cy)
    z_lo, z_hi = float(V[:, 2].min()), float(V[:, 2].max())
    prof = []
    edges = np.linspace(z_lo, z_hi, 9)
    for i in range(len(edges) - 1):
        sel = (V[:, 2] >= edges[i]) & (V[:, 2] <= edges[i + 1])
        if sel.sum() == 0:
            continue
        rr = r[sel]
        prof.append({"z": round(0.5 * (edges[i] + edges[i + 1]), 5),
                     "r_min": round(float(rr.min()), 5), "r_max": round(float(rr.max()), 5),
                     "r_mean": round(float(rr.mean()), 5), "n": int(sel.sum())})
    top = V[V[:, 2] > z_hi - 0.008]
    rt = np.hypot(top[:, 0] - cx, top[:, 1] - cy)
    return {"vertex_derived": True, "n_verts": int(len(V)),
            "z": [round(z_lo, 5), round(z_hi, 5)], "height_m": round(z_hi - z_lo, 5),
            "outer_diameter_m": round(2.0 * float(r.max()), 5),
            "outer_radius_m": round(float(r.max()), 5),
            "rim_radius_top_band_m": [round(float(rt.min()), 5), round(float(rt.max()), 5)],
            "radial_profile": prof}


def collision_geometry(sim, bid, centre):
    """Vertex-derived geometry of the BOX geoms: those are the only geoms that collide."""
    boxes = []
    for g in geom_ids(sim, bid):
        cs = box_world_corners(sim, g)
        if not cs:
            continue
        zs = [c[2] for c in cs]
        cx = sum(c[0] for c in cs) / 8.0
        cy = sum(c[1] for c in cs) / 8.0
        rad = [math.hypot(c[0] - float(centre[0]), c[1] - float(centre[1])) for c in cs]
        boxes.append({"geom": g,
                      "z": [round(min(zs), 5), round(max(zs), 5)],
                      "radius_center": round(math.hypot(cx - float(centre[0]),
                                                        cy - float(centre[1])), 5),
                      "radius_range": [round(min(rad), 5), round(max(rad), 5)],
                      "size": [round(float(x), 5) for x in sim.model.geom_size[g]],
                      "contype": int(sim.model.geom_contype[g]),
                      "conaffinity": int(sim.model.geom_conaffinity[g])})
    if not boxes:
        return {"n_geoms": 0}
    z_top = max(b["z"][1] for b in boxes)
    z_bot = min(b["z"][0] for b in boxes)
    top = [b for b in boxes if b["z"][1] > z_top - 0.010]
    # exact radial clearance from the object's vertical axis to the nearest collision box,
    # per z band: 0 means solid material directly under the gripper's centre
    bands = []
    for lo, hi, tag in ((z_top - 0.004, z_top, "top_4mm"),
                        (z_top - 0.010, z_top, "top_10mm"),
                        (0.5 * (z_bot + z_top) - 0.005, 0.5 * (z_bot + z_top) + 0.005, "mid_10mm")):
        sel = [b for b in boxes if b["z"][1] >= lo and b["z"][0] <= hi]
        if not sel:
            bands.append({"band": tag, "n": 0, "axis_clearance_m": None})
            continue
        d = []
        for b in sel:
            cs = box_world_corners(sim, b["geom"])
            d.append(point_box_xy_distance(float(centre[0]), float(centre[1]),
                                           [(c[0], c[1]) for c in cs]))
        bands.append({"band": tag, "n": len(sel),
                      "axis_clearance_m": round(min(d), 5),
                      "max_axis_clearance_m": round(max(d), 5)})
    return {"n_geoms": len(boxes),
            "axis_clearance_bands": bands,
            "z": [round(z_bot, 5), round(z_top, 5)],
            "height_m": round(z_top - z_bot, 5),
            "top_rim_z": round(z_top, 5),
            "n_top_plates": len(top),
            "top_plate_radius_m": round(sum(b["radius_center"] for b in top) / len(top), 5),
            "top_plate_radius_range_m": [round(min(b["radius_range"][0] for b in top), 5),
                                         round(max(b["radius_range"][1] for b in top), 5)],
            "top_plate_thickness_m": round(min(min(b["size"]) for b in top), 5),
            "outer_diameter_m": round(2.0 * max(b["radius_range"][1] for b in boxes), 5),
            "contype_any": sorted({b["contype"] for b in boxes}),
            "conaffinity_any": sorted({b["conaffinity"] for b in boxes}),
            "boxes": boxes}


def visual_geoms_note(sim, bid):
    out = []
    for g in geom_ids(sim, bid):
        t = int(sim.model.geom_type[g])
        if t != 7:
            continue
        out.append({"geom": g, "type": "mesh",
                    "contype": int(sim.model.geom_contype[g]),
                    "conaffinity": int(sim.model.geom_conaffinity[g]),
                    "rbound": round(float(sim.model.geom_rbound[g]), 5)})
    return out


def obj_sites(sim, bid):
    """Sites that belong to the object body: robosuite places objects by their bottom_site."""
    names = list(sim.model.site_names) if hasattr(sim.model, "site_names") else []
    out = []
    for s in range(sim.model.nsite):
        if int(sim.model.site_bodyid[s]) != bid:
            continue
        out.append({"name": names[s] if s < len(names) else "site%d" % s,
                    "local": [round(float(x), 5) for x in sim.model.site_pos[s]],
                    "world": [round(float(x), 5) for x in sim.data.site_xpos[s]]})
    return out


def controller_grasp_z(sim, bid, frac=FRAC):
    """Exactly the retry controller's formula (evobot_libero_retry.py lines 88-95)."""
    zs = []
    for g in geom_ids(sim, bid):
        c = sim.data.geom_xpos[g]
        rb = float(sim.model.geom_rbound[g])
        zs.append((float(c[2]) - rb, float(c[2]) + rb))
    z_lo = min(z[0] for z in zs)
    z_hi = max(z[1] for z in zs)
    return {"z_lo": round(z_lo, 5), "z_hi": round(z_hi, 5),
            "implied_height_m": round(z_hi - z_lo, 5),
            "grasp_z": round(z_lo + frac * (z_hi - z_lo), 5)}


def goal_vec(pr):
    """The retry controller's own goal lookup: site if present, else the region body + 3 cm."""
    sim, region = pr.sim, pr.region
    sites = list(sim.model.site_names)
    bodies = list(sim.model.body_names)
    if region in sites:
        return [float(x) for x in sim.data.site_xpos[sim.model.site_name2id(region)]]
    cand = region + "_contain_region"
    if cand in sites:
        return [float(x) for x in sim.data.site_xpos[sim.model.site_name2id(cand)]]
    rb = region + "_main" if (region + "_main") in bodies else next(
        (b for b in bodies if b.startswith(region)), None)
    if rb is None:
        return [0.0, 0.0, 0.95]
    pos = [float(x) for x in sim.data.body_xpos[bodies.index(rb)]]
    return [pos[0], pos[1], pos[2] + 0.03]


# ---------------------------------------------------------------- environment scaffolding
class Probe:
    def __init__(self, idx):
        self.idx = idx
        self.name, self.bddl, self.init = task_files(idx)
        self.pairs = parse_goal(open(self.bddl, encoding="utf-8").read())
        self.obj, self.region = self.pairs[0]
        self.env = make_env(self.bddl)
        self.env.set_init_state(load_init(self.init))
        self.sim = self.env.env.sim
        self.sim.forward()
        self.bodies = list(self.sim.model.body_names)
        self.obj_body = find_obj_body(self.sim, self.obj)
        self.bid = body_index(self.sim, self.obj_body)
        self.obj_geoms = set(geom_ids(self.sim, self.bid))
        self.fbbodies = set(finger_bodies(self.sim))
        self.fbgeoms = set(g for g in range(self.sim.model.ngeom)
                           if int(self.sim.model.geom_bodyid[g]) in self.fbbodies)
        self.site = self.sim.model.site_name2id("gripper0_grip_site")
        self.fj = finger_joints(self.sim)
        self.fbadr = [j["qposadr"] for j in self.fj]
        self.done = {"v": False}

    def step(self, a):
        if self.done["v"]:
            return False
        try:
            _o, _r, d, _i = self.env.step(a)
        except ValueError:
            self.done["v"] = True
            return False
        self.done["v"] = bool(d)
        return True

    def eef(self):
        return [float(x) for x in self.sim.data.site_xpos[self.site]]

    def objpos(self):
        return [float(x) for x in self.sim.data.body_xpos[self.bid]]

    def gap(self):
        """Finger opening in metres. The two finger joints have mirrored ranges
        ([0, 0.04] and [-0.04, 0]), so the opening is q1 - q2, not the sum."""
        q = [float(self.sim.data.qpos[a]) for a in self.fbadr]
        return float(q[0] - q[1]) if len(q) >= 2 else 0.0

    def contacts(self):
        o_f = o_other = 0
        for i in range(self.sim.data.ncon):
            c = self.sim.data.contact[i]
            s = {int(c.geom1), int(c.geom2)}
            if s & self.obj_geoms:
                if s & self.fbgeoms:
                    o_f += 1
                else:
                    o_other += 1
        return o_f, o_other

    def drive(self, target, gripper, steps=240, tol=0.010):
        for _ in range(steps):
            err = [target[i] - self.eef()[i] for i in range(3)]
            n = math.sqrt(sum(e * e for e in err))
            if n <= tol or self.done["v"]:
                return True
            a = [0.0] * 7
            for i in range(3):
                a[i] = max(-1.0, min(1.0, err[i] * K_POS))
            a[6] = gripper
            self.step(a)
        return False

    def settle(self, steps=SETTLE_STEPS):
        for _ in range(steps):
            a = [0.0] * 7
            a[6] = GRIP_OPEN
            self.step(a)

    def close(self, steps=22):
        for _ in range(steps):
            a = [0.0] * 7
            a[6] = GRIP_CLOSE
            self.step(a)

    def open(self, steps=20):
        for _ in range(steps):
            a = [0.0] * 7
            a[6] = GRIP_OPEN
            self.step(a)

    def lift(self, dz=0.14, max_steps=240, trace_every=8):
        start = self.eef()
        zs = []
        for k in range(max_steps):
            cur = self.eef()
            err = [0.0, 0.0, (start[2] + dz) - cur[2]]
            if self.done["v"]:
                break
            a = [0.0] * 7
            for i in range(3):
                a[i] = max(-1.0, min(1.0, err[i] * K_POS))
            a[6] = GRIP_CLOSE
            self.step(a)
            if k % trace_every == 0:
                zs.append(round(self.objpos()[2], 5))
        return zs

    def close_env(self):
        try:
            self.env.close()
        except Exception:
            pass


def _reaches(bands, tag, half_clearance):
    """True if solid material lies within one jaw half-clearance of the object's vertical axis.

    A centred top grasp can only pinch something if the object has material near its own axis;
    a bowl rim is a ring whose inner radius is larger than the jaw half-clearance.
    """
    v = next((b["axis_clearance_m"] for b in bands if b["band"] == tag), None)
    if v is None:
        return None
    return bool(v <= half_clearance)


# ---------------------------------------------------------------- census
def census_one(idx):
    p = Probe(idx)
    t0_body = p.objpos()
    t0 = {"obj_body_pos": [round(x, 5) for x in t0_body],
          "visual": visual_geometry(p.sim, p.bid, t0_body),
          "collision": collision_geometry(p.sim, p.bid, t0_body),
          "controller": controller_grasp_z(p.sim, p.bid),
          "pads": pad_geometry(p.sim),
          "sites": obj_sites(p.sim, p.bid),
          "gripper_open_qpos_gap": round(p.gap(), 5),
          "eef": [round(x, 5) for x in p.eef()]}
    table_top = table_top_z(p.sim)
    p.settle()
    t1_body = p.objpos()
    t1 = {"obj_body_pos": [round(x, 5) for x in t1_body],
          "visual": visual_geometry(p.sim, p.bid, t1_body),
          "collision": collision_geometry(p.sim, p.bid, t1_body),
          "controller": controller_grasp_z(p.sim, p.bid),
          "pads": pad_geometry(p.sim),
          "sites": obj_sites(p.sim, p.bid),
          "eef": [round(x, 5) for x in p.eef()],
          "contacts": p.contacts(),
          "obj_geoms_note": visual_geoms_note(p.sim, p.bid)}
    fj = finger_joints(p.sim)
    max_open = sum(j["range"][1] - j["range"][0] for j in fj)
    rec = {"index": idx, "task": p.name, "suite": SUITE,
           "obj": p.obj, "region": p.region, "obj_body": p.obj_body,
           "table_top_z": round(table_top, 5) if table_top is not None else None,
           "closing_axis_xy": [round(x, 4) for x in closing_axis(p.sim)],
           "gripper": {"finger_joints": [{"name": j["name"], "range": j["range"]} for j in fj],
                       "max_opening_m": round(max_open, 5)},
           "init_pose": t0, "settled": t1,
           "drop_m": round(t1_body[2] - t0_body[2], 5),
           "drop_xy_m": round(math.hypot(t1_body[0] - t0_body[0],
                                         t1_body[1] - t0_body[1]), 5)}
    # the two numbers that decide the mechanism
    ctrl_z = t0["controller"]["grasp_z"]
    rim_settled = t1["collision"].get("top_rim_z")
    vis_rim_settled = t1["visual"].get("z", [None, None])[1]
    rec["verdict_numbers"] = {
        "ctrl_grasp_z_at_init_pose": ctrl_z,
        "settled_collision_rim_z": rim_settled,
        "settled_visual_rim_z": vis_rim_settled,
        "ctrl_grasp_z_minus_settled_collision_rim_m": round(ctrl_z - rim_settled, 5)
        if rim_settled is not None else None,
        "ctrl_grasp_z_minus_settled_visual_rim_m": round(ctrl_z - vis_rim_settled, 5)
        if vis_rim_settled is not None else None,
        "max_opening_minus_collision_outer_diameter_m": round(
            max_open - t1["collision"].get("outer_diameter_m", 0.0), 5),
        "max_opening_minus_visual_outer_diameter_m": round(
            max_open - t1["visual"].get("outer_diameter_m", 0.0), 5),
        "ctrl_implied_height_minus_true_collision_height_m": round(
            t0["controller"]["implied_height_m"] - t1["collision"].get("height_m", 0.0), 5),
        "bound_extends_below_table_at_init": bool(
            t0["controller"]["z_lo"] < (table_top or 0.0)),
        "bound_extends_below_table_at_settled": bool(
            t1["controller"]["z_lo"] < (table_top or 0.0)),
        "jaw_half_clearance_m": round((t1["pads"].get("pad_gap_m") or 0.0) / 2.0, 5),
        "axis_clearance_top_4mm_m": next(
            (b["axis_clearance_m"] for b in t1["collision"].get("axis_clearance_bands", [])
             if b["band"] == "top_4mm"), None),
        "axis_clearance_mid_10mm_m": next(
            (b["axis_clearance_m"] for b in t1["collision"].get("axis_clearance_bands", [])
             if b["band"] == "mid_10mm"), None),
        "centred_grasp_reaches_material_top_band": _reaches(
            t1["collision"].get("axis_clearance_bands", []), "top_4mm",
            (t1["pads"].get("pad_gap_m") or 0.0) / 2.0),
        "centred_grasp_reaches_material_mid_band": _reaches(
            t1["collision"].get("axis_clearance_bands", []), "mid_10mm",
            (t1["pads"].get("pad_gap_m") or 0.0) / 2.0),
        "top_band_min_radius_m": t1["collision"].get("top_plate_radius_range_m", [None])[0],
        "top_band_is_ring": bool(
            t1["collision"].get("top_plate_radius_range_m", [0.0])[0]
            > (t1["pads"].get("pad_gap_m") or 0.0) / 2.0),
        "collision_outer_diameter_m": t1["collision"].get("outer_diameter_m"),
        "collision_height_m": t1["collision"].get("height_m"),
    }
    rec["eef_pose_at_init"] = t0["eef"]
    p.close_env()
    return rec


# ---------------------------------------------------------------- settle
def settle_one(idx, steps=120, report_every=20):
    p = Probe(idx)
    z0 = p.objpos()
    mesh0 = visual_geometry(p.sim, p.bid, z0)
    box0 = collision_geometry(p.sim, p.bid, z0)
    trace = []
    settled_at = None
    quiet = 0
    prev = z0
    for k in range(steps):
        a = [0.0] * 7
        a[6] = GRIP_OPEN
        p.step(a)
        cur = p.objpos()
        d = math.sqrt(sum((cur[i] - prev[i]) ** 2 for i in range(3)))
        quiet = quiet + 1 if d < 0.0005 else 0
        prev = cur
        if settled_at is None and quiet >= 10:
            settled_at = k + 1
        if (k + 1) % report_every == 0:
            pos = p.objpos()
            v = visual_geometry(p.sim, p.bid, pos)
            c = collision_geometry(p.sim, p.bid, pos)
            trace.append({"step": k + 1, "body_z": round(pos[2], 5),
                          "visual_z": v.get("z"), "collision_z": c.get("z"),
                          "contacts": p.contacts()})
    pos = p.objpos()
    rec = {"index": idx, "task": p.name, "obj": p.obj, "obj_body": p.obj_body,
           "table_top_z": (round(table_top_z(p.sim), 5)
                           if table_top_z(p.sim) is not None else None),
           "t0": {"body_pos": [round(x, 5) for x in z0],
                  "visual_z": mesh0.get("z"), "collision_z": box0.get("z")},
           "t_end": {"body_pos": [round(x, 5) for x in pos],
                     "visual_z": visual_geometry(p.sim, p.bid, pos).get("z"),
                     "collision_z": collision_geometry(p.sim, p.bid, pos).get("z"),
                     "contacts": p.contacts()},
           "trace": trace,
           "dz_body": round(pos[2] - z0[2], 5),
           "settle_rule": {"per_step_disp_m": 0.0005, "consecutive_quiet_steps": 10,
                           "max_steps": steps, "settled_at_step": settled_at},
           "log": ["%d zero-action steps from the set_init_state pose" % steps]}
    p.close_env()
    return rec


# ---------------------------------------------------------------- trials
CONFIGS = {
    # the two controller modes, replicated: grasp z from the pre-settle bounding-sphere midpoint
    "ctrl_top_center": dict(approach="top", xy="center", z="ctrl"),
    "ctrl_side_center": dict(approach="side_x", xy="center", z="ctrl"),
    # pose fixed (grasp z recomputed after the object settled), arithmetic unchanged
    "top_center_settledgz": dict(approach="top", xy="center", z="ctrl_settled"),
    # correct height (settled physical rim), still centred
    "top_center_rimz": dict(approach="top", xy="center", z="rim-0.015"),
    # rim pinch: offset along the jaw closing axis so the pads straddle the rim plate
    "rim_pinch": dict(approach="top", xy="rim", z="plate_mid"),
    "rim_pinch_hi": dict(approach="top", xy="rim", z="plate_top"),
    "rim_pinch_lo": dict(approach="top", xy="rim", z="plate_bottom"),
    "rim_pinch_side": dict(approach="side_x", xy="rim", z="plate_mid"),
    # rim pinch, then carry to the goal and release: does the official predicate accept it?
    "rim_pinch_place": dict(approach="top", xy="rim", z="plate_mid", place=True),
    # falsification: rotate the wrist first, then offset along the OLD world axis
    "rim_pinch_staleaxis": dict(approach="top", xy="rim", z="plate_mid", yaw_steps=90),
    # guard condition: the same offset applied BLINDLY to a solid object, vs a centred grasp
    "blind_offset_mid": dict(approach="top", xy="rim", z="coll_mid"),
    "top_center_collmid": dict(approach="top", xy="center", z="coll_mid"),
}


def trial_one(idx, cfg_name):
    cfg = CONFIGS[cfg_name]
    p = Probe(idx)
    ctrl = controller_grasp_z(p.sim, p.bid)          # computed where the controller computes it
    p.settle()                                        # the episode steps before the arm arrives
    centre = p.objpos()
    coll = collision_geometry(p.sim, p.bid, centre)
    vis = visual_geometry(p.sim, p.bid, centre)
    pads = pad_geometry(p.sim)
    axis = closing_axis(p.sim)

    ctrl_settled = controller_grasp_z(p.sim, p.bid)     # same formula, fresh pose
    z_map = {"ctrl": ctrl["grasp_z"],
             "ctrl_settled": ctrl_settled["grasp_z"],
             "rim-0.015": (coll.get("top_rim_z") or vis["z"][1]) - 0.015,
             "plate_mid": coll["z"][1] - 0.008,
             "plate_top": coll["z"][1] - 0.002,
             "plate_bottom": coll["z"][1] - 0.020,
             "coll_mid": 0.5 * (coll["z"][0] + coll["z"][1])}
    axis0 = closing_axis(p.sim)                 # axis before any wrist rotation
    if cfg.get("yaw_steps"):
        for _ in range(int(cfg["yaw_steps"])):
            a = [0.0] * 7
            a[3:6] = [0.0, 0.0, 1.0]
            a[6] = GRIP_OPEN
            p.step(a)
    axis_now = closing_axis(p.sim)
    axis = axis0 if cfg.get("yaw_steps") else axis_now
    z_target = z_map[cfg["z"]]
    if cfg["xy"] == "center":
        xy = [centre[0], centre[1]]
        r_off = 0.0
    else:
        r_off = coll["top_plate_radius_m"]
        xy = [centre[0] + r_off * axis[0], centre[1] + r_off * axis[1]]

    if cfg["approach"] == "top":
        p.drive([xy[0], xy[1], max(ctrl["z_hi"], coll["z"][1]) + 0.12], GRIP_OPEN)
        p.drive([xy[0], xy[1], z_target], GRIP_OPEN, tol=0.008)
    else:
        start = [centre[0] + STANDOFF, centre[1], z_target]
        p.drive([start[0], start[1], max(ctrl["z_hi"], coll["z"][1]) + 0.12], GRIP_OPEN)
        p.drive(start, GRIP_OPEN)
        p.drive([centre[0], centre[1], z_target], GRIP_OPEN, tol=0.012)

    eef_grasp = p.eef()
    o_before = p.objpos()
    gap_open = p.gap()
    pad_open = pad_geometry(p.sim)
    p.close()
    gap_closed = p.gap()
    pad_closed = pad_geometry(p.sim)
    f_close, oth_close = p.contacts()
    o_after_close = p.objpos()
    zs = p.lift()
    gap_lift = p.gap()
    f_lift, oth_lift = p.contacts()
    o_after = p.objpos()
    lift = o_after[2] - o_before[2]
    peak = (max(zs) - o_before[2]) if zs else 0.0

    place = None
    if cfg.get("place"):
        goal = goal_vec(p)
        p.drive([goal[0], goal[1], goal[2] + 0.10], GRIP_CLOSE)
        err_xy = None
        for _ in range(4):
            o = p.objpos()
            err_xy = math.hypot(o[0] - goal[0], o[1] - goal[1])
            if err_xy <= 0.005:
                break
            cur = p.eef()
            p.drive([cur[0] - (o[0] - goal[0]), cur[1] - (o[1] - goal[1]),
                     min(cur[2], goal[2] + 0.05)], GRIP_CLOSE, tol=0.006)
        p.open(20)
        for _ in range(120):
            a = [0.0] * 7
            a[6] = GRIP_OPEN
            p.step(a)
        place = {"goal": [round(x, 5) for x in goal],
                 "release_xy_err_m": round(err_xy, 5) if err_xy is not None else None,
                 "official_success": bool(p.env.check_success()),
                 "obj_final": [round(x, 5) for x in p.objpos()]}

    rec = {"index": idx, "task": p.name, "config": cfg_name,
           "obj": p.obj, "obj_body": p.obj_body,
           "z_target": round(z_target, 5),
           "eef_at_grasp": [round(x, 5) for x in eef_grasp],
           "eef_z_minus_target_m": round(eef_grasp[2] - z_target, 5),
           "xy_target": [round(x, 5) for x in xy],
           "rim_offset_m": round(r_off, 5),
           "closing_axis_xy_used": [round(x, 4) for x in axis] if axis else None,
           "closing_axis_xy_at_grasp": [round(x, 4) for x in axis_now] if axis_now else None,
           "wrist_yaw_commanded_steps": cfg.get("yaw_steps", 0),
           "gap_open_m": round(gap_open, 5),
           "gap_after_close_m": round(gap_closed, 5),
           "gap_during_lift_m": round(gap_lift, 5),
           "pad_gap_open_m": (pad_open or {}).get("pad_gap_m"),
           "pad_gap_after_close_m": (pad_closed or {}).get("pad_gap_m"),
           "pad_z_range_world_at_grasp": (pad_open or {}).get("pad_z_range_world"),
           "contacts_obj_finger_after_close": f_close,
           "contacts_obj_other_after_close": oth_close,
           "contacts_obj_finger_during_lift": f_lift,
           "contacts_obj_other_during_lift": oth_lift,
           "obj_before": [round(x, 5) for x in o_before],
           "obj_after_close": [round(x, 5) for x in o_after_close],
           "obj_after": [round(x, 5) for x in o_after],
           "obj_xy_displacement_m": round(math.hypot(o_after[0] - o_before[0],
                                                     o_after[1] - o_before[1]), 5),
           "lift_m": round(lift, 5),
           "peak_lift_m": round(peak, 5),
           "carried": bool(lift > LIFT_PROOF_M),
           "obj_z_trace": zs[::3],
           "place": place,
           "geom": {"ctrl_at_init": ctrl,
                    "ctrl_at_settled": ctrl_settled,
                    "settled_collision": {k: coll[k] for k in
                                          ("z", "height_m", "top_rim_z", "n_top_plates",
                                           "top_plate_radius_m", "top_plate_thickness_m",
                                           "outer_diameter_m") if k in coll},
                    "settled_visual": {k: vis[k] for k in
                                       ("z", "height_m", "outer_diameter_m") if k in vis},
                    "pads_at_settle": pads},
           "terminated": p.done["v"]}
    p.close_env()
    return rec



# ---------------------------------------------------------------- jaw-axis probe
def axis_one(idx):
    """Is the jaw-closing axis fixed in the world, or does it follow the gripper yaw?

    Three independent definitions are recorded, because the answer must be one a controller
    can compute at run time:
      A. the vector between the two finger bodies, projected on xy  (what the trials use)
      B. each finger joint's slide axis taken from the model and rotated into the world
         (jnt_axis is expressed in the joint body's frame, so world = R_body @ jnt_axis)
      C. the hand body's own frame axes
    """
    p = Probe(idx)
    bodies = list(p.sim.model.body_names)
    hand = next((c for c in ("robot0_right_hand", "gripper0_base", "robot0_eef")
                 if c in bodies), None)
    hbid = bodies.index(hand) if hand else None
    jn = list(p.sim.model.joint_names)
    samples = []

    def matvec(R, v):
        return [sum(R[i][j] * v[j] for j in range(3)) for i in range(3)]

    def sample(tag):
        ax = closing_axis(p.sim)
        Rh = [list(row) for row in p.sim.data.body_xmat[hbid].reshape(3, 3)] if hbid is not None else None
        ax_local = ([round(sum(Rh[j][i] * ax[j] for j in range(3)), 4) for i in range(3)]
                    if (ax is not None and Rh is not None) else None)
        slides = []
        for j in p.fj:
            jb = int(p.sim.model.jnt_bodyid[j["jid"]])
            Rj = [list(row) for row in p.sim.data.body_xmat[jb].reshape(3, 3)]
            w = matvec(Rj, [float(x) for x in p.sim.model.jnt_axis[j["jid"]]])
            n = math.sqrt(sum(x * x for x in w)) or 1.0
            slides.append({"joint": j["name"], "body": bodies[jb],
                           "axis_world": [round(x / n, 4) for x in w],
                           "axis_in_hand": ([round(sum(Rh[k][i] * w[k] for k in range(3)) / n, 4)
                                             for i in range(3)] if Rh else None)})
        hand_axes = None
        if Rh is not None:
            hand_axes = {"x_world": [round(Rh[i][0], 4) for i in range(3)],
                         "y_world": [round(Rh[i][1], 4) for i in range(3)],
                         "z_world": [round(Rh[i][2], 4) for i in range(3)]}
        samples.append({"tag": tag, "eef": [round(x, 5) for x in p.eef()],
                        "A_finger_pair_xy": [round(x, 4) for x in ax] if ax else None,
                        "A_in_hand_frame": ax_local,
                        "A_yaw_deg": round(math.degrees(math.atan2(ax[1], ax[0])), 2) if ax else None,
                        "B_finger_joint_slide_axes": slides,
                        "C_hand_frame": hand_axes})

    def yaw(steps, sign):
        for _ in range(steps):
            a = [0.0] * 7
            a[3:6] = [0.0, 0.0, float(sign)]
            a[6] = GRIP_OPEN
            p.step(a)

    sample("init")
    p.settle()
    sample("after_settle")
    centre = p.objpos()
    coll = collision_geometry(p.sim, p.bid, centre)
    p.drive([centre[0], centre[1], coll["z"][1] + 0.14], GRIP_OPEN)
    sample("above_bowl")
    yaw(60, +1)
    sample("after_yaw_plus_60")
    yaw(120, -1)
    sample("after_yaw_minus_120")

    def const(key):
        vals = {tuple(s[key]) for s in samples if s.get(key)}
        return len(vals) == 1

    rec = {"index": idx, "task": p.name, "suite": SUITE, "hand_body": hand, "samples": samples,
           "A_constant_world": const("A_finger_pair_xy"),
           "A_constant_in_hand_frame": const("A_in_hand_frame"),
           "A_yaw_range_deg": [min(s["A_yaw_deg"] for s in samples if s["A_yaw_deg"] is not None),
                               max(s["A_yaw_deg"] for s in samples if s["A_yaw_deg"] is not None)],
           "B_constant_world": len({tuple(x["axis_world"]) for s in samples
                                    for x in s["B_finger_joint_slide_axes"]}) == 1,
           "B_constant_in_hand_frame": len({tuple(x["axis_in_hand"]) for s in samples
                                            for x in s["B_finger_joint_slide_axes"]
                                            if x["axis_in_hand"]}) == 1,
           "B_antiparallel": all(
               len(s["B_finger_joint_slide_axes"]) == 2 and all(
                   abs(s["B_finger_joint_slide_axes"][0]["axis_world"][i]
                       + s["B_finger_joint_slide_axes"][1]["axis_world"][i]) < 0.02
                   for i in range(3)) for s in samples)}
    p.close_env()
    return rec



# ---------------------------------------------------------------- blockers probe
def blockers_one(idx):
    """On the tasks where the rim-pinch descent stalled, which bodies stopped the gripper?

    A stall is only a grasp failure if the object itself is what stops the hand. If a drawer,
    a cookie box or the stove is in the way, that is a reach problem and must be reported as one.
    """
    p = Probe(idx)
    p.settle()
    centre = p.objpos()
    coll = collision_geometry(p.sim, p.bid, centre)
    axis = closing_axis(p.sim)
    r_off = coll["top_plate_radius_m"]
    xy = [centre[0] + r_off * axis[0], centre[1] + r_off * axis[1]]
    z_target = coll["z"][1] - 0.008
    p.drive([xy[0], xy[1], coll["z"][1] + 0.14], GRIP_OPEN)
    bodies = list(p.sim.model.body_names)
    touched = {}
    for _ in range(240):
        err = [xy[0] - p.eef()[0], xy[1] - p.eef()[1], z_target - p.eef()[2]]
        if math.sqrt(sum(e * e for e in err)) <= 0.008:
            break
        a = [0.0] * 7
        for i in range(3):
            a[i] = max(-1.0, min(1.0, err[i] * K_POS))
        a[6] = GRIP_OPEN
        p.step(a)
        for i in range(p.sim.data.ncon):
            c = p.sim.data.contact[i]
            s = {int(c.geom1), int(c.geom2)}
            if not (s & p.fbgeoms):
                continue
            other = (s - p.fbgeoms).pop() if (s - p.fbgeoms) else None
            if other is None:
                continue
            b = bodies[int(p.sim.model.geom_bodyid[other])]
            touched[b] = touched.get(b, 0) + 1
    stall_pose = p.eef()
    # reach test: same height, xy pulled 8 cm toward the robot base. If that reaches, the stall
    # is the arm's kinematic limit at that xy, not a collision and not a grasp failure.
    base = None
    for cand in ("robot0_base", "robot0_link0", "robot0_base_link"):
        if cand in bodies:
            base = [float(x) for x in p.sim.data.body_xpos[bodies.index(cand)]]
            break
    reach = None
    if base is not None:
        v = [stall_pose[0] - base[0], stall_pose[1] - base[1]]
        n = math.hypot(*v) or 1.0
        xy2 = [stall_pose[0] - 0.08 * v[0] / n, stall_pose[1] - 0.08 * v[1] / n]
        p.drive([xy2[0], xy2[1], stall_pose[2] + 0.15], GRIP_OPEN)
        for _ in range(240):
            err = [xy2[0] - p.eef()[0], xy2[1] - p.eef()[1], z_target - p.eef()[2]]
            if math.sqrt(sum(e * e for e in err)) <= 0.008:
                break
            a = [0.0] * 7
            for i in range(3):
                a[i] = max(-1.0, min(1.0, err[i] * K_POS))
            a[6] = GRIP_OPEN
            p.step(a)
        reach = {"xy": [round(x, 5) for x in xy2],
                 "eef": [round(x, 5) for x in p.eef()],
                 "z_error_m": round(p.eef()[2] - z_target, 5),
                 "reached": bool(abs(p.eef()[2] - z_target) <= 0.012)}
    rec = {"index": idx, "task": p.name, "obj": p.obj,
           "z_target": round(z_target, 5), "eef_stalled_at": [round(x, 5) for x in stall_pose],
           "stall_m": round(stall_pose[2] - z_target, 5),
           "bodies_touching_fingers": sorted(touched.items(), key=lambda kv: -kv[1]),
           "obj_body_touched": any(b.startswith(p.obj) for b, _ in touched.items()),
           "robot_base": [round(x, 5) for x in base] if base else None,
           "radial_distance_at_stall_m": round(math.hypot(stall_pose[0] - base[0],
                                                          stall_pose[1] - base[1]), 5) if base else None,
           "reach_test_8cm_closer": reach}
    p.close_env()
    return rec


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["census", "trials", "settle", "axis", "blockers"])
    ap.add_argument("--suite", default="libero_spatial")
    ap.add_argument("--tasks", default="0")
    ap.add_argument("--configs", default="ctrl_top_center")
    ap.add_argument("--out", default="/tmp/evobot_bowl")
    args = ap.parse_args()
    global SUITE
    SUITE = args.suite
    tasks = [int(x) for x in args.tasks.split(",") if x.strip() != ""]
    os.makedirs(args.out, exist_ok=True)
    t0 = time.time()

    if args.mode == "blockers":
        for idx in tasks:
            rec = blockers_one(idx)
            json.dump(rec, open(os.path.join(args.out, "blockers_%d.json" % idx), "w"), indent=2)
            print(json.dumps({"blockers": idx, "task": rec["task"],
                              "stall_m": rec["stall_m"],
                              "bodies": rec["bodies_touching_fingers"],
                              "obj_touched": rec["obj_body_touched"],
                              "radial_m": rec["radial_distance_at_stall_m"],
                              "reach_test": rec["reach_test_8cm_closer"]}), flush=True)
        return 0

    if args.mode == "axis":
        for idx in tasks:
            rec = axis_one(idx)
            json.dump(rec, open(os.path.join(args.out, "axis_%s_%d.json" % (SUITE, idx)), "w"),
                      indent=2)
            print(json.dumps({"axis": idx, "task": rec["task"],
                              "A_axes": [(s["tag"], s["A_finger_pair_xy"], s["A_yaw_deg"])
                                         for s in rec["samples"]],
                              "A_const_world": rec["A_constant_world"],
                              "A_const_hand": rec["A_constant_in_hand_frame"],
                              "A_yaw_range": rec["A_yaw_range_deg"],
                              "B_const_world": rec["B_constant_world"],
                              "B_const_hand": rec["B_constant_in_hand_frame"],
                              "B_antiparallel": rec["B_antiparallel"],
                              "B_first": rec["samples"][0]["B_finger_joint_slide_axes"]},
                             default=str), flush=True)
        return 0

    if args.mode == "census":
        for idx in tasks:
            rec = census_one(idx)
            json.dump(rec, open(os.path.join(args.out, "census_%d.json" % idx), "w"), indent=2)
            v = rec["verdict_numbers"]
            print(json.dumps({"census": idx, "task": rec["task"],
                              "gz": v["ctrl_grasp_z_at_init_pose"],
                              "settled_coll_rim": v["settled_collision_rim_z"],
                              "gz_minus_rim": v["ctrl_grasp_z_minus_settled_collision_rim_m"],
                              "drop": rec["drop_m"],
                              "max_open": rec["gripper"]["max_opening_m"],
                              "coll_outer_dia": rec["settled"]["collision"].get("outer_diameter_m"),
                              "dt_s": round(time.time() - t0, 1)}), flush=True)
        return 0

    if args.mode == "settle":
        for idx in tasks:
            rec = settle_one(idx)
            json.dump(rec, open(os.path.join(args.out, "settle_%d.json" % idx), "w"), indent=2)
            print(json.dumps({"settle": idx, "task": rec["task"],
                              "table_top_z": rec["table_top_z"],
                              "t0_body_z": rec["t0"]["body_pos"][2],
                              "t_end_body_z": rec["t_end"]["body_pos"][2],
                              "dz_body": rec["dz_body"],
                              "t0_collision_z": rec["t0"]["collision_z"],
                              "t_end_collision_z": rec["t_end"]["collision_z"],
                              "contacts_end": rec["t_end"]["contacts"]}), flush=True)
        return 0

    for idx in tasks:
        for cfg_name in [c for c in args.configs.split(",") if c]:
            rec = trial_one(idx, cfg_name)
            json.dump(rec, open(os.path.join(args.out, "trial_%d_%s.json" % (idx, cfg_name)), "w"),
                      indent=2)
            print(json.dumps({"trial": idx, "cfg": cfg_name,
                              "z_target": rec["z_target"],
                              "eef_z": rec["eef_at_grasp"][2],
                              "gap_close": rec["gap_after_close_m"],
                              "con_f": rec["contacts_obj_finger_after_close"],
                              "lift": rec["lift_m"], "peak": rec["peak_lift_m"],
                              "carried": rec["carried"],
                              "dt_s": round(time.time() - t0, 1)}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())