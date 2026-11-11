#!/usr/bin/env python3
"""Measure what the two failing tall bottles ARE, before trying another grasp.

WHY THIS EXISTS: three earlier rounds aimed the gripper at a number derived from
geom_xpos +- geom_rbound, and both tall bottles still never lifted.  geom_rbound is the
bounding-SPHERE radius of a geom, so for an elongated object it reports a vertical extent that
is much larger than the object and, in this scene, starts below the table.  This script measures
the real world-space axis-aligned extent of every collision geom (box corners / mesh vertices),
the height profile of the object, and the gripper's own envelope, so that a grasp height is a
measured quantity instead of a number that happens to work for a can.

PHASE=measure writes raw geometry; PHASE=matrix runs the grasp variants.
"""
import json
import os
import re
import sys

ROOT = "/mnt/c/Users/fuker/Desktop/workspace/ext-bench/LIBERO"
sys.path.insert(0, ROOT)

SUITE = os.environ.get("LIBERO_SUITE", "libero_object")
IDX = int(os.environ.get("LIBERO_TASK", "2"))
OUTDIR = os.environ.get("LIBERO_OUTDIR", "/tmp/libero_tall")
PHASE = os.environ.get("PHASE", "measure")

# MuJoCo geom type enum
MESH, BOX, SPHERE = 7, 6, 2


def task_name(idx, suite=SUITE):
    import importlib.util
    p = os.path.join(ROOT, "libero", "libero", "benchmark", "libero_suite_task_map.py")
    spec = importlib.util.spec_from_file_location("tm", p)
    tm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tm)
    return tm.libero_task_map[suite][idx]


def parse_goal(bddl_text):
    start = bddl_text.find("(:goal")
    pairs = re.findall(r"\((?:On|In)\s+([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\)", bddl_text[start:])
    return [(o, r) for o, r in pairs if r.endswith("_region")]


def task_paths(idx, suite=SUITE):
    name = task_name(idx, suite)
    bddl = os.path.join(ROOT, "libero", "libero", "bddl_files", suite, name + ".bddl")
    init = os.path.join(ROOT, "libero", "libero", "init_files", suite, name + ".pruned_init")
    return name, bddl, init


def make_env(bddl, init):
    import numpy as np
    import torch
    from libero.libero.envs import OffScreenRenderEnv
    kw = dict(bddl_file_name=bddl, camera_heights=64, camera_widths=64)
    if os.environ.get("NEWOBS", "1") == "0":
        kw["use_camera_obs"] = False        # physics is identical; only the pixels are skipped
    env = OffScreenRenderEnv(**kw)
    env.reset()
    st = torch.load(init, map_location="cpu", weights_only=False)
    arr = st.detach().cpu().numpy() if hasattr(st, "detach") else np.asarray(st)
    k = int(os.environ.get("INIT_IDX", "0"))
    env.set_init_state(arr[k % len(arr)])
    env.init_index = k
    return env


def geom_aabb(sim, g, np):
    """True world-space AABB of one geom.  Box: 8 rotated corners.  Mesh: its vertices.
    Everything else falls back to the bounding sphere (and is flagged as such)."""
    t = int(field(sim.model, "type", g))
    pos = np.array(sim.data.geom_xpos[g], dtype=float)
    mat = np.array(sim.data.geom_xmat[g], dtype=float).reshape(3, 3)
    if t == BOX:
        size = np.array(field(sim.model, "size", g), dtype=float)
        corners = np.array([[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)],
                           dtype=float) * size
        pts = corners @ mat.T + pos
        return pts.min(0), pts.max(0), "box"
    if t == MESH:
        mid = int(field(sim.model, "dataid", g))
        if mid >= 0:
            a = int(sim.model.mesh_vertadr[mid]); n = int(sim.model.mesh_vertnum[mid])
            verts = np.array(sim.model.mesh_vert[a:a + n], dtype=float)
            pts = verts @ mat.T + pos
            return pts.min(0), pts.max(0), "mesh"
    if t == SPHERE:
        r = float(field(sim.model, "size", g)[0])
        return pos - r, pos + r, "sphere"
    rb = float(field(sim.model, "rbound", g))
    return pos - rb, pos + rb, "rbound"


def body_geoms(sim, bid):
    return [g for g in range(sim.model.ngeom) if int(field(sim.model, "bodyid", g)) == bid]


def field(model, name, i):
    """Read a per-geom field whichever spelling this mujoco/robosuite build exposes."""
    for cand in ("geom_" + name, name):
        v = getattr(model, cand, None)
        if v is not None:
            return v[i]
    raise AttributeError("no geom field %r on %r" % (name, type(model).__name__))


def collision(sim, g):
    """A geom participates in contact if contype|conaffinity is non-zero."""
    return (int(field(sim.model, "contype", g)) | int(field(sim.model, "conaffinity", g))) != 0


def gname(model, g):
    names = getattr(model, "geom_names", None)
    if names is not None:
        return names[g] or ""
    try:
        import mujoco
        return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, g) or ""
    except Exception:
        return ""


def profile(sim, bid, np, step=0.005):
    """Width of the object along world x and y, per 5 mm height slab."""
    gids = [g for g in body_geoms(sim, bid) if collision(sim, g)]
    boxes = []
    for g in gids:
        lo, hi, kind = geom_aabb(sim, g, np)
        boxes.append((lo, hi, kind))
    if not boxes:
        return []
    zlo = min(b[0][2] for b in boxes); zhi = max(b[1][2] for b in boxes)
    rows = []
    n = max(1, int(round((zhi - zlo) / step)))
    for i in range(n):
        a = zlo + i * step; b = a + step
        xs, ys = [], []
        for lo, hi, kind in boxes:
            if hi[2] > a and lo[2] < b:      # slab overlap
                xs.append((lo[0], hi[0])); ys.append((lo[1], hi[1]))
        row = {"z0": round(a, 4), "z1": round(b, 4), "n": len(xs)}
        if xs:
            row["x"] = [round(min(v[0] for v in xs), 4), round(max(v[1] for v in xs), 4)]
            row["y"] = [round(min(v[0] for v in ys), 4), round(max(v[1] for v in ys), 4)]
            row["wx"] = round(row["x"][1] - row["x"][0], 4)
            row["wy"] = round(row["y"][1] - row["y"][0], 4)
        rows.append(row)
    return rows


def main_measure():
    import numpy as np
    name, bddl, init = task_paths(IDX)
    pairs = parse_goal(open(bddl, encoding="utf-8").read())
    obj, region = pairs[0]
    env = make_env(bddl, init)
    sim = env.env.sim
    bodies = list(sim.model.body_names)
    sites = list(sim.model.site_names)
    bid = bodies.index(obj + "_main") if (obj + "_main") in bodies else next(
        i for i, b in enumerate(bodies) if b.startswith(obj))
    rec = {"task": name, "index": IDX, "obj": obj, "region": region,
           "obj_body": bodies[bid], "ngeom": int(sim.model.ngeom), "nbody": len(bodies)}

    # --- the object: every geom, with the two different ways of bounding it
    geoms = []
    for g in body_geoms(sim, bid):
        lo, hi, kind = geom_aabb(sim, g, np)
        c = np.array(sim.data.geom_xpos[g], dtype=float)
        rb = float(field(sim.model, "rbound", g))
        geoms.append({
            "gid": g, "type": int(field(sim.model, "type", g)), "kind": kind,
            "name": gname(sim.model, g),
            "collision": bool(collision(sim, g)),
            "contype": int(field(sim.model, "contype", g)),
            "conaffinity": int(field(sim.model, "conaffinity", g)),
            "c": [round(float(v), 5) for v in c],
            "rbound": round(rb, 5),
            "rbound_box": [round(float(c[2] - rb), 5), round(float(c[2] + rb), 5)],
            "aabb_lo": [round(float(v), 5) for v in lo],
            "aabb_hi": [round(float(v), 5) for v in hi],
        })
    rec["geoms"] = geoms
    coll = [g for g in geoms if g["collision"]]
    allo = np.array([g["aabb_lo"] for g in geoms], dtype=float)
    allhi = np.array([g["aabb_hi"] for g in geoms], dtype=float)
    rec["aabb_all"] = [[round(float(v), 5) for v in allo.min(0)], [round(float(v), 5) for v in allhi.max(0)]]
    if coll:
        clo = np.array([g["aabb_lo"] for g in coll], dtype=float)
        chi = np.array([g["aabb_hi"] for g in coll], dtype=float)
        rec["aabb_collision"] = [[round(float(v), 5) for v in clo.min(0)],
                                 [round(float(v), 5) for v in chi.max(0)]]
        rec["height_collision_m"] = round(float(chi[:, 2].max() - clo[:, 2].min()), 4)
        rec["width_collision_m"] = [round(float(chi[:, i].max() - clo[:, i].min()), 4) for i in range(3)]
        rec["lowest_geoms"] = sorted(coll, key=lambda g: g["aabb_lo"][2])[:6]
    # what the OLD rule (bounding sphere) would have aimed at
    old_lo = min(g["rbound_box"][0] for g in geoms); old_hi = max(g["rbound_box"][1] for g in geoms)
    rec["rbound_extent"] = [round(old_lo, 4), round(old_hi, 4)]
    rec["rbound_grasp_z_frac0.5"] = round(old_lo + 0.5 * (old_hi - old_lo), 4)
    rec["body_pos"] = [round(float(v), 5) for v in sim.data.body_xpos[bid]]
    rec["body_quat"] = [round(float(v), 5) for v in sim.data.body_xquat[bid]]
    rec["mass_total"] = round(float(sum(sim.model.body_mass[i] for i in range(sim.model.nbody)
                                       if sim.model.body_rootid[i] == sim.model.body_rootid[bid])), 5)
    rec["profile_5mm"] = profile(sim, bid, np)

    # --- the support surface: which body is the object resting on
    surf = []
    for bi, b in enumerate(bodies):
        nm = b.lower()
        if "floor" in nm or "table" in nm:
            gl = body_geoms(sim, bi)
            if not gl:
                continue
            zs = []
            for g in gl:
                lo, hi, kind = geom_aabb(sim, g, np)
                zs.append((float(lo[2]), float(hi[2])))
            surf.append({"body": b, "z_top": round(max(z[1] for z in zs), 5),
                         "z_bottom": round(min(z[0] for z in zs), 5)})
    rec["support"] = surf
    rec["workspace_offset_hint"] = "problem z_offset=-0.025, floor_offset z=-0.035 (libero_floor_manipulation.py)"

    # --- the gripper: what it can enclose, and where the pads sit relative to the grip site
    site = sim.model.site_name2id("gripper0_grip_site")
    gs = np.array(sim.data.site_xpos[site], dtype=float)
    gnames = [gname(sim.model, g) for g in range(sim.model.ngeom)]
    pads = [g for g in range(sim.model.ngeom) if "pad_collision" in (gnames[g] or "")]
    fingers = [g for g in range(sim.model.ngeom)
               if "finger" in (gnames[g] or "") and "pad" not in (gnames[g] or "")
               and collision(sim, g)]
    jnames = list(getattr(sim.model, "joint_names", [""] * sim.model.njnt))
    zs = [sim.model.jnt_range[i] for i in range(sim.model.njnt) if "finger_joint" in (jnames[i] or "")]
    rec["gripper"] = {
        "grip_site": [round(float(v), 5) for v in gs],
        "finger_joint_ranges": [[round(float(a), 4), round(float(b), 4)] for a, b in zs],
        "pad_geoms": [gnames[g] for g in pads],
        "pad_pos_open": [[round(float(v), 5) for v in sim.data.geom_xpos[g]] for g in pads],
        "finger_geoms": [gnames[g] for g in fingers],
        "finger_aabb": [[[round(float(v), 4) for v in geom_aabb(sim, g, np)[0]],
                         [round(float(v), 4) for v in geom_aabb(sim, g, np)[1]]] for g in fingers],
    }
    if len(pads) >= 2:
        p = np.array([sim.data.geom_xpos[g] for g in pads], dtype=float)
        rec["gripper"]["pad_separation_open_m"] = round(float(np.linalg.norm(p[0] - p[1])), 5)
        d = p[0] - p[1]
        rec["gripper"]["pad_axis_world"] = [round(float(v), 4) for v in d / np.linalg.norm(d)]
        rec["gripper"]["pad_center"] = [round(float(v), 5) for v in p.mean(0)]
        rec["gripper"]["pad_center_minus_grip_site"] = [round(float(v), 5) for v in (p.mean(0) - gs)]
    # --- how wide can the gripper actually open / how far does it close?  measure, do not assume
    jids = [i for i in range(sim.model.njnt) if "finger_joint" in (jnames[i] or "")]

    def finger_state():
        q = [round(float(sim.data.qpos[sim.model.jnt_qposadr[j]]), 5) for j in jids]
        pos = [np.array(sim.data.geom_xpos[g], dtype=float) for g in pads]
        sep = round(float(np.linalg.norm(pos[0] - pos[1])), 5) if len(pos) >= 2 else None
        # exact inner-face gap: the pads close along world y here (axis reported above)
        gap = None
        if len(pads) >= 2:
            bb = [geom_aabb(sim, g, np) for g in pads]
            a, b = bb[0][0][1], bb[1][1][1]      # top of pad0 vs bottom of pad1 in y
            gap = round(float(abs(b - a)), 5) if abs(b - a) > 0 else round(float(abs(bb[1][0][1] - bb[0][1][1])), 5)
        return {"qpos": q, "pad_separation_m": sep, "inner_gap_y_m": gap,
                "pad_pos": [[round(float(v), 5) for v in p] for p in pos]}

    def safe_step(a):
        try:
            env.step(a)
            return True
        except ValueError:
            return False

    rec["gripper"]["at_reset"] = finger_state()
    for _ in range(30):
        if not safe_step(np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0])):
            break
    rec["gripper"]["forced_open"] = finger_state()
    for _ in range(40):
        if not safe_step(np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0])):
            break
    rec["gripper"]["forced_closed"] = finger_state()
    rec["env_meta"] = {"z_offset": getattr(env.env, "z_offset", None)}
    os.makedirs(OUTDIR, exist_ok=True)
    json.dump(rec, open(os.path.join(OUTDIR, "measure_%d.json" % IDX), "w"), indent=2)
    print(json.dumps({k: rec[k] for k in ("task", "obj", "aabb_collision", "rbound_extent",
                                          "rbound_grasp_z_frac0.5", "height_collision_m",
                                          "width_collision_m", "support", "body_pos")}, indent=2))
    print(json.dumps(rec["gripper"], indent=2))
    env.close()
    return 0



# =============================================================== shared machinery
K_POS = 18.0
GRIP_OPEN = -1.0
GRIP_CLOSE = 1.0
LIFT_PROOF_M = 0.03


def rnd(v, n=4):
    return [round(float(x), n) for x in v]


class Ctx(object):
    pass


class Rig(object):
    """Thin wrapper that survives the robosuite trap: after an episode ends (done == success
    predicate true) the next step() raises, so a refusal is treated as termination."""

    def __init__(self, env, sim):
        self.env, self.sim = env, sim
        self.site = sim.model.site_name2id("gripper0_grip_site")
        self.terminated = False
        self.n = 0

    def eef(self):
        import numpy as np
        return np.array(self.sim.data.site_xpos[self.site], dtype=float)

    def rot(self):
        import numpy as np
        return np.array(self.sim.data.site_xmat[self.site], dtype=float).reshape(3, 3)

    def step(self, a):
        import numpy as np
        if self.terminated:
            return
        try:
            _o, _r, done, _i = self.env.step(np.asarray(a, dtype=float))
        except ValueError:
            self.terminated = True
            return
        self.n += 1
        self.terminated = bool(done)

    def drive(self, target, gripper, steps=200, tol=0.008, stop=None):
        import numpy as np
        target = np.asarray(target, dtype=float)
        for _ in range(steps):
            if self.terminated:
                return False
            err = target - self.eef()
            if float(np.linalg.norm(err)) <= tol:
                return True
            if stop is not None and stop():
                return False
            a = np.zeros(7)
            a[:3] = np.clip(err * K_POS, -1.0, 1.0)
            a[6] = gripper
            self.step(a)
        return False

    def squeeze(self, gripper, steps):
        import numpy as np
        for _ in range(steps):
            a = np.zeros(7)
            a[6] = gripper
            self.step(a)

    def pose_to(self, target, target_R=None, gripper=GRIP_OPEN, steps=240, tol=0.008,
                rot_tol=0.06):
        """Position + orientation P-control on the OSC action.  Needed because these grasps
        are not all top-down: a lateral approach has to rotate the wrist before moving in."""
        import numpy as np
        from robosuite.utils.control_utils import orientation_error
        target = np.asarray(target, dtype=float)
        for _ in range(steps):
            if self.terminated:
                return False
            err = target - self.eef()
            rerr = np.zeros(3) if target_R is None else np.asarray(
                orientation_error(target_R, self.rot()), dtype=float)
            if (float(np.linalg.norm(err)) <= tol
                    and (target_R is None or float(np.linalg.norm(rerr)) <= rot_tol)):
                return True
            a = np.zeros(7)
            a[:3] = np.clip(err * K_POS, -1.0, 1.0)
            a[3:6] = np.clip(rerr * 4.0, -1.0, 1.0)
            a[6] = gripper
            self.step(a)
        return False

    def rot_delta(self, axis, angle):
        """World-frame rotation by <angle> about world <axis>, applied to the current pose."""
        import numpy as np
        c, s = float(np.cos(angle)), float(np.sin(angle))
        if axis == "y":
            Rd = np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])
        elif axis == "x":
            Rd = np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])
        else:
            Rd = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
        return Rd @ self.rot()

    def yaw_to(self, yaw, gripper, steps=80, tol=0.06):
        import numpy as np
        for _ in range(steps):
            R = self.rot()
            cur = float(np.arctan2(R[1, 0], R[0, 0]))
            err = (yaw - cur + np.pi) % (2 * np.pi) - np.pi
            if abs(err) <= tol:
                return True
            a = np.zeros(7)
            a[3:6] = np.clip(np.array([0.0, 0.0, err]) * 3.0, -1.0, 1.0)
            a[6] = gripper
            self.step(a)
        return False


def load(idx, suite=None):
    import numpy as np
    suite = suite or SUITE
    name, bddl, init = task_paths(idx, suite)
    pairs = parse_goal(open(bddl, encoding="utf-8").read())
    obj, region = pairs[0]
    env = make_env(bddl, init)
    sim = env.env.sim
    ctx = Ctx()
    ctx.env, ctx.sim, ctx.name, ctx.obj, ctx.region = env, sim, name, obj, region
    bodies = list(sim.model.body_names)
    sites = list(sim.model.site_names)
    ctx.bodies, ctx.sites = bodies, sites
    ctx.obj_body = obj + "_main" if (obj + "_main") in bodies else next(
        b for b in bodies if b.startswith(obj))
    ctx.bid = bodies.index(ctx.obj_body)
    ctx.rig = Rig(env, sim)
    if region in sites:
        ctx.goal = np.array(sim.data.site_xpos[sim.model.site_name2id(region)], dtype=float)
        ctx.goal_kind = "site"
    else:
        cand = region + "_contain_region"
        if cand in sites:
            ctx.goal = np.array(sim.data.site_xpos[sim.model.site_name2id(cand)], dtype=float)
            ctx.goal_kind = "site"
        else:
            rb_ = region + "_main" if (region + "_main") in bodies else next(
                (b for b in bodies if b.startswith(region)), None)
            ctx.goal = np.array(sim.data.body_xpos[bodies.index(rb_)], dtype=float) + np.array([0, 0, 0.03])
            ctx.goal_kind = "object"
    return ctx


def obj_aabb(ctx, collision_only=True):
    import numpy as np
    gids = body_geoms(ctx.sim, ctx.bid)
    if collision_only:
        gids = [g for g in gids if collision(ctx.sim, g)]
    lo = np.array([1e9, 1e9, 1e9]); hi = -lo
    for g in gids:
        a, b, _k = geom_aabb(ctx.sim, g, np)
        lo = np.minimum(lo, a); hi = np.maximum(hi, b)
    return lo, hi


def obj_pos(ctx):
    import numpy as np
    return np.array(ctx.sim.data.body_xpos[ctx.bid], dtype=float)


def obj_quat(ctx):
    import numpy as np
    return np.array(ctx.sim.data.body_xquat[ctx.bid], dtype=float)


def obj_linvel(ctx):
    import numpy as np
    d = getattr(ctx.sim.data, "_data", None)
    try:
        return np.array(ctx.sim.data.cvel[ctx.sim.model.body_dofadr[ctx.bid]], dtype=float)
    except Exception:
        return np.zeros(6)


def active_contacts(ctx):
    """Every active contact as (geom name, geom name, penetration distance)."""
    sim = ctx.sim
    out = []
    try:
        n = int(sim.data.ncon)
    except Exception:
        n = 0
    for i in range(n):
        g1 = g2 = -1
        dist = 0.0
        try:
            c = sim.data.contact[i]
            try:
                g1 = int(c["geom1"]); g2 = int(c["geom2"]); dist = float(c["dist"])
            except Exception:
                g1 = int(c.geom1); g2 = int(c.geom2); dist = float(c.dist)
        except Exception:
            continue
        out.append((gname(sim.model, g1), gname(sim.model, g2), round(dist, 5)))
    return out


def gripper_contacts(ctx):
    return [c for c in active_contacts(ctx)
            if "gripper" in (c[0] or "") or "gripper" in (c[1] or "")]


def landmarks(ctx):
    """Measured grasp landmarks: true extent, the narrowest slab in the upper half (neck),
    and the extent the old bounding-sphere rule produced."""
    import numpy as np
    sim = ctx.sim
    lo, hi = obj_aabb(ctx)
    prof = profile(sim, ctx.bid, np, 0.005)
    z_lo, z_hi = float(lo[2]), float(hi[2])
    upper = [r for r in prof if r.get("wx") is not None and r["z0"] >= z_lo + 0.55 * (z_hi - z_lo)]
    neck = min(upper, key=lambda r: r["wx"] + r["wy"]) if upper else None
    old_lo, old_hi = None, None
    rb = []
    for g in body_geoms(sim, ctx.bid):
        c = np.array(sim.data.geom_xpos[g], dtype=float)
        r = float(field(sim.model, "rbound", g))
        rb.append([float(c[2] - r), float(c[2] + r)])
    old_lo = min(r[0] for r in rb); old_hi = max(r[1] for r in rb)
    out = {
        "extent_true": [round(z_lo, 4), round(z_hi, 4)],
        "height_true": round(z_hi - z_lo, 4),
        "extent_rbound": [round(old_lo, 4), round(old_hi, 4)],
        "grasp_z_rbound_frac0.5": round(old_lo + 0.5 * (old_hi - old_lo), 4),
        "grasp_z_true_mid": round(z_lo + 0.5 * (z_hi - z_lo), 4),
    }
    # MEASURED hand clearance: the hand body's lowest point sits this far above the grip site
    # (descend_2.json shows hand/object contact at eef z 0.1093 against an object top of
    # 0.1456 -> 36.3 mm).  A top-down grasp therefore cannot reach more than that far below an
    # object's top, so the neck rule is only applicable to objects TALLER than 2x that.
    hand_clearance = 0.0363
    out["hand_clearance_below_grip_m"] = hand_clearance
    out["tall_object"] = bool((z_hi - z_lo) > 2.0 * hand_clearance)
    if neck:
        out["neck_z"] = round(0.5 * (neck["z0"] + neck["z1"]), 4)
        out["neck_width_xy"] = [neck["wx"], neck["wy"]]
        out["neck_slab"] = [neck["z0"], neck["z1"]]
    else:
        out["neck_z"] = out["grasp_z_true_mid"]
        out["neck_width_xy"] = None
        out["neck_slab"] = None
    # A short, wide object has no "neck": the gripper simply closes around it from the top, and
    # aiming at a slab of it is worse than aiming at its middle.  Guard the rule by the object's
    # own measured height, not by which task it is.
    if not out["tall_object"]:
        out["grasp_rule"] = "true_mid (object shorter than 2x hand clearance: no neck to reach)"
        out["neck_z"] = out["grasp_z_true_mid"]
    else:
        out["grasp_rule"] = "neck (object taller than 2x hand clearance)"
    out["centre"] = rnd(obj_pos(ctx))
    out["profile"] = prof
    return out


def settle_world(ctx, n=25):
    """Let the scene settle before measuring anything.

    MEASURED, NOT ASSUMED: at t0 these bottles are spawned with their collision geometry
    BELOW the floor plane and the contact solver ejects them within one step.  A measurement
    taken at t0 therefore describes a pose the object never has when the gripper arrives.
    """
    import numpy as np
    p0 = obj_pos(ctx)
    lo0, hi0 = obj_aabb(ctx)
    trace = []
    for k in range(n):
        if ctx.rig.terminated:
            break
        a = np.zeros(7)
        ctx.rig.step(a)
        if k in (0, 1, 2, 3, 5, 8, 12, n - 1):
            lo, hi = obj_aabb(ctx)
            p = obj_pos(ctx)
            trace.append({"k": k + 1,
                          "dz": round(float(p[2] - p0[2]), 4),
                          "dxy": round(float(np.linalg.norm(p[:2] - p0[:2])), 4),
                          "aabb_z": [round(float(lo[2]), 4), round(float(hi[2]), 4)]})
    lo, hi = obj_aabb(ctx)
    return {"t0_aabb": [rnd(lo0), rnd(hi0)], "settled_aabb": [rnd(lo), rnd(hi)],
            "t0_center": rnd(p0), "settled_center": rnd(obj_pos(ctx)),
            "settle_dz": round(float(obj_pos(ctx)[2] - p0[2]), 4),
            "settle_dxy": round(float(np.linalg.norm(obj_pos(ctx)[:2] - p0[:2])), 4),
            "trace": trace}


# =============================================================== phases
SETTLE_AT = (1, 2, 3, 5, 8, 12, 20, 30, 50, 80, 120, 160, 200)


def write_json(name, rec):
    os.makedirs(OUTDIR, exist_ok=True)
    p = os.path.join(OUTDIR, name)
    json.dump(rec, open(p, "w"), indent=2)
    return p


def main_settle():
    """Does the object move on its own before the robot touches it?"""
    import numpy as np
    ctx = load(IDX)
    lo, hi = obj_aabb(ctx)
    p0, q0 = obj_pos(ctx), obj_quat(ctx)
    rec = {"phase": "settle", "task": ctx.name, "index": IDX, "obj": ctx.obj,
           "t0": {"pos": rnd(p0), "quat": rnd(q0), "aabb": [rnd(lo), rnd(hi)],
                  "ncon": len(active_contacts(ctx))},
           "rows": []}
    for k in range(1, max(SETTLE_AT) + 1):
        if ctx.rig.terminated:
            break
        ctx.rig.step(np.zeros(7))
        if k in SETTLE_AT:
            lo2, hi2 = obj_aabb(ctx)
            p = obj_pos(ctx)
            rec["rows"].append({
                "k": k,
                "dxy": round(float(np.linalg.norm(p[:2] - p0[:2])), 4),
                "dz": round(float(p[2] - p0[2]), 4),
                "aabb_z": [round(float(lo2[2]), 4), round(float(hi2[2]), 4)],
                "quat": rnd(obj_quat(ctx)),
                "ncon": len(active_contacts(ctx)),
                "obj_contacts": [c for c in active_contacts(ctx)
                                 if ctx.obj in (c[0] or "") or ctx.obj in (c[1] or "")][:8],
            })
    rec["terminated"] = ctx.rig.terminated
    write_json("settle_%d.json" % IDX, rec)
    print(json.dumps({"task": ctx.name, "t0": rec["t0"], "last": rec["rows"][-1] if rec["rows"] else None},
                     indent=2))
    ctx.env.close()
    return 0


def main_descend():
    """Drive straight down over the object and record what stops the gripper."""
    import numpy as np
    ctx = load(IDX)
    rig = ctx.rig
    settle = settle_world(ctx)
    lm = landmarks(ctx)
    lo, hi = obj_aabb(ctx)
    centre = obj_pos(ctx)
    z_lo, z_hi = float(lo[2]), float(hi[2])
    rig.squeeze(GRIP_OPEN, 25)
    pre = rig.drive((centre[0], centre[1], z_hi + 0.12), GRIP_OPEN, steps=260)
    rec = {"phase": "descend", "task": ctx.name, "index": IDX, "obj": ctx.obj,
           "settle": settle,
           "landmarks": {k: v for k, v in lm.items() if k != "profile"},
           "pregrasp": {"reached": bool(pre), "eef": rnd(rig.eef())},
           "rows": []}
    zs = []
    for k in range(140):
        if rig.terminated:
            break
        eef = rig.eef()
        a = np.zeros(7)
        a[0] = float(np.clip((centre[0] - eef[0]) * K_POS, -1.0, 1.0))
        a[1] = float(np.clip((centre[1] - eef[1]) * K_POS, -1.0, 1.0))
        a[2] = -0.10                      # 5 mm of commanded descent per step
        a[6] = GRIP_OPEN
        before = obj_pos(ctx)
        rig.step(a)
        eef2 = rig.eef()
        after = obj_pos(ctx)
        zs.append(float(eef2[2]))
        gcs = gripper_contacts(ctx)
        rec["rows"].append({"k": k, "eef": rnd(eef2), "dz": round(float(eef2[2] - eef[2]), 4),
                            "obj_dz": round(float(after[2] - before[2]), 4),
                            "obj_dxy": round(float(np.linalg.norm(after[:2] - before[:2])), 4),
                            "ncon": len(active_contacts(ctx)), "gcon": gcs[:8]})
        if float(np.linalg.norm(after[:2] - centre[:2])) > 0.02 or abs(float(after[2] - centre[2])) > 0.02:
            rec["object_moved"] = {"k": k, "eef": rnd(eef2), "obj": rnd(after), "gcon": gcs}
            break
        if len(zs) > 8 and abs(zs[-1] - zs[-9]) < 0.0015:
            rec["blocked"] = {"k": k, "eef": rnd(eef2), "gcon": gcs,
                              "reason": "commanded descent produced < 1.5 mm over 8 steps"}
            break
        if float(eef2[2]) < z_lo - 0.005:
            rec["reached_bottom"] = {"k": k, "eef": rnd(eef2)}
            break
    rec["terminated"] = rig.terminated
    write_json("descend_%d.json" % IDX, rec)
    print(json.dumps({"task": ctx.name, "landmarks": rec["landmarks"],
                      "pregrasp": rec["pregrasp"],
                      "blocked": rec.get("blocked"),
                      "object_moved": rec.get("object_moved"),
                      "reached_bottom": rec.get("reached_bottom")}, indent=2))
    ctx.env.close()
    return 0


VARIANTS = ["rbound_mid", "cap", "neck", "side_neck", "side_horiz", "side_horiz_neck",
            "neck_preclose", "neck_yaw90", "push_then_neck"]

SIDE_STANDOFF = 0.16          # how far to +x the lateral approach starts


def grasp_plan(lm, variant):
    """Decide where to stand, where to aim, and which way to point the gripper.

    Everything comes from measured landmarks on the settled object, not from a constant.
    """
    import numpy as np
    c = np.array(lm["centre"], dtype=float)
    z_lo, z_hi = float(lm["extent_true"][0]), float(lm["extent_true"][1])
    up = z_hi + 0.12
    z_mid = lm["grasp_z_true_mid"]
    z_neck = lm["neck_z"]
    if variant == "rbound_mid":            # the rule that fails today (bounding sphere, pre-settle pose)
        return {"approach": "top", "pre": (c[0], c[1], up),
                "grasp": (c[0], c[1], lm["grasp_z_rbound_frac0.5"]), "yaw": 0.0, "pitch_y": 0.0}
    if variant == "true_mid":
        return {"approach": "top", "pre": (c[0], c[1], up),
                "grasp": (c[0], c[1], z_mid), "yaw": 0.0, "pitch_y": 0.0}
    if variant == "neck":
        return {"approach": "top", "pre": (c[0], c[1], up),
                "grasp": (c[0], c[1], z_neck), "yaw": 0.0, "pitch_y": 0.0}
    if variant == "cap":                   # the top 1.5 cm are still reachable under the hand
        return {"approach": "top", "pre": (c[0], c[1], up),
                "grasp": (c[0], c[1], z_hi - 0.015), "yaw": 0.0, "pitch_y": 0.0}
    if variant == "neck_preclose":
        return {"approach": "top", "pre": (c[0], c[1], up),
                "grasp": (c[0], c[1], z_neck), "yaw": 0.0, "pitch_y": 0.0}
    if variant == "neck_yaw90":
        return {"approach": "top", "pre": (c[0], c[1], up),
                "grasp": (c[0], c[1], z_neck), "yaw": np.pi / 2, "pitch_y": 0.0}
    if variant == "side_neck":             # vertical gripper, horizontal approach at neck height
        return {"approach": "side", "pre": (c[0] + SIDE_STANDOFF, c[1], z_neck + 0.01),
                "grasp": (c[0], c[1], z_neck), "yaw": 0.0, "pitch_y": 0.0}
    if variant == "side_horiz":            # wrist rotated 90 deg: tool axis horizontal, pads straddle y
        return {"approach": "side_h", "pre": (c[0] + SIDE_STANDOFF, c[1], z_mid),
                "grasp": (c[0], c[1], z_mid), "yaw": 0.0, "pitch_y": np.pi / 2}
    if variant == "side_horiz_neck":
        return {"approach": "side_h", "pre": (c[0] + SIDE_STANDOFF, c[1], z_neck),
                "grasp": (c[0], c[1], z_neck), "yaw": 0.0, "pitch_y": np.pi / 2}
    if variant == "push_then_neck":
        return {"approach": "top", "pre": (c[0], c[1], up),
                "grasp": (c[0], c[1], z_neck), "yaw": 0.0, "pitch_y": 0.0}
    raise KeyError(variant)


def attempt(idx, variant, suite=None):
    """One fresh environment, one grasp variant, one official success verdict."""
    import numpy as np
    ctx = load(idx, suite)
    rig = ctx.rig
    settle = settle_world(ctx)          # the object is spawned under the floor; let it land
    lm = landmarks(ctx)                 # measure the pose the object ACTUALLY has
    c = np.array(lm["centre"], dtype=float)
    plan = grasp_plan(lm, variant)
    pre = np.array(plan["pre"], dtype=float)
    gr = np.array(plan["grasp"], dtype=float)
    z_hi = float(lm["extent_true"][1])
    rec = {"variant": variant, "index": idx, "task": ctx.name, "obj": ctx.obj,
           "settle": settle,
           "landmarks": {k: v for k, v in lm.items() if k != "profile"},
           "plan": {"approach": plan["approach"], "pregrasp": rnd(pre), "grasp": rnd(gr),
                    "yaw_deg": round(float(np.degrees(plan["yaw"])), 1),
                    "pitch_y_deg": round(float(np.degrees(plan["pitch_y"])), 1)},
           "events": []}
    obj0 = obj_pos(ctx)
    rig.squeeze(GRIP_OPEN, 25)
    R_target = None
    if plan["pitch_y"]:
        # raise, rotate the wrist, then come in from the side
        rig.drive((pre[0], pre[1], z_hi + 0.14), GRIP_OPEN, steps=240, tol=0.012)
        rig.pose_to((pre[0], pre[1], z_hi + 0.14), rig.rot_delta("y", plan["pitch_y"]),
                    GRIP_OPEN, steps=140, tol=0.015, rot_tol=0.08)
        R_target = rig.rot_delta("y", 0.0)
        rec["events"].append({"ev": "rotate", "eef": rnd(rig.eef()),
                              "xmat": rnd(rig.rot().reshape(9), 3)})
        rig.pose_to((pre[0], pre[1], pre[2]), R_target, GRIP_OPEN, steps=240, tol=0.010)
        rec["events"].append({"ev": "standoff", "eef": rnd(rig.eef())})
        ok_grasp = rig.pose_to((gr[0], gr[1], gr[2]), R_target, GRIP_OPEN, steps=200, tol=0.008)
    elif plan["approach"] == "side":
        rig.drive((pre[0], pre[1], z_hi + 0.14), GRIP_OPEN, steps=240, tol=0.012)
        rig.drive(pre, GRIP_OPEN, steps=200, tol=0.010)
        rec["events"].append({"ev": "standoff", "eef": rnd(rig.eef())})
        ok_grasp = rig.drive(gr, GRIP_OPEN, steps=200, tol=0.008)
    else:
        ok_grasp = rig.drive(pre, GRIP_OPEN, steps=260, tol=0.012)
        rec["events"].append({"ev": "pregrasp", "ok": bool(ok_grasp), "eef": rnd(rig.eef())})
        if variant == "neck_yaw90":
            y_ok = rig.yaw_to(plan["yaw"], GRIP_OPEN)
            rec["events"].append({"ev": "yaw", "ok": bool(y_ok),
                                  "yaw_deg": round(float(np.degrees(np.arctan2(
                                      rig.rot()[1, 0], rig.rot()[0, 0]))), 1)})
        if variant == "push_then_neck":
            rig.drive((gr[0], gr[1], gr[2] + 0.06), GRIP_OPEN, steps=140, tol=0.010)
            rig.drive((gr[0], gr[1] + 0.10, gr[2] + 0.02), GRIP_OPEN, steps=80, tol=0.012)
            rec["events"].append({"ev": "push", "eef": rnd(rig.eef()), "obj": rnd(obj_pos(ctx))})
            c2 = obj_pos(ctx)
            gr = np.array([float(c2[0]), float(c2[1]), float(gr[2])])
        if variant == "neck_preclose":
            rig.drive((gr[0], gr[1], gr[2] + 0.05), GRIP_OPEN, steps=140, tol=0.010)
            rig.squeeze(0.45, 12)
            ok_grasp = rig.drive(gr, 0.45, steps=160, tol=0.006)
        else:
            rig.drive((gr[0], gr[1], gr[2] + 0.02), GRIP_OPEN, steps=180, tol=0.010)
            ok_grasp = rig.drive(gr, GRIP_OPEN, steps=180, tol=0.006)
    rec["events"].append({"ev": "grasp_pose", "reached": bool(ok_grasp), "eef": rnd(rig.eef()),
                          "target": rnd(gr), "obj": rnd(obj_pos(ctx)),
                          "gcon": gripper_contacts(ctx)[:10]})
    before = obj_pos(ctx)
    rig.squeeze(GRIP_CLOSE, 28)
    if R_target is not None:
        rig.pose_to((rig.eef()[0], rig.eef()[1], rig.eef()[2] + 0.14), R_target, GRIP_CLOSE,
                    steps=200, tol=0.010)
    else:
        rig.drive((rig.eef()[0], rig.eef()[1], rig.eef()[2] + 0.14), GRIP_CLOSE, steps=200)
    after = obj_pos(ctx)
    dz = float(after[2] - before[2])
    dxy = float(np.linalg.norm(after[:2] - before[:2]))
    carried = dz > LIFT_PROOF_M
    rec["lift"] = {"obj_before": rnd(before), "obj_after": rnd(after),
                   "dz": round(dz, 4), "dxy": round(dxy, 4), "carried": bool(carried),
                   "obj_aabb_z": [round(float(obj_aabb(ctx)[0][2]), 4),
                                  round(float(obj_aabb(ctx)[1][2]), 4)]}
    if not carried:
        rec["official_success"] = False
        rec["note"] = "grasp did not carry the object (lift %.3f m)" % dz
        rec["object_displaced_m"] = round(float(np.linalg.norm(obj_pos(ctx) - obj0)), 4)
        write_json("matrix_%d_%s.json" % (idx, variant), rec)
        print(json.dumps({"task": idx, "variant": variant, "carried": False,
                          "dz_mm": round(1000 * dz, 1), "success": False,
                          "grasp_pose_reached": bool(ok_grasp),
                          "eef_z": rec["events"][-1]["eef"][2],
                          "target_z": round(float(gr[2]), 4),
                          "displaced_mm": round(1000 * rec["object_displaced_m"], 1)}, indent=2))
        ctx.env.close()
        return rec
    # carry to the basket and release only when the OBJECT is over the region
    d = ctx.goal
    if R_target is not None:
        rig.pose_to((d[0], d[1], d[2] + 0.10), R_target, GRIP_CLOSE, steps=260, tol=0.012)
    else:
        rig.drive((d[0], d[1], d[2] + 0.10), GRIP_CLOSE, steps=260, tol=0.012)
    rel = None
    for _ in range(4):
        o = obj_pos(ctx)
        e = float(np.hypot(o[0] - d[0], o[1] - d[1]))
        rec["events"].append({"ev": "release_check", "obj_xy_err": round(e, 4), "obj": rnd(o)})
        if e <= 0.006:
            rel = e
            break
        cur = rig.eef()
        if R_target is not None:
            rig.pose_to((cur[0] - (o[0] - d[0]), cur[1] - (o[1] - d[1]),
                         min(cur[2], d[2] + 0.05)), R_target, GRIP_CLOSE, steps=140, tol=0.008)
        else:
            rig.drive((cur[0] - (o[0] - d[0]), cur[1] - (o[1] - d[1]),
                       min(cur[2], d[2] + 0.05)), GRIP_CLOSE, steps=140, tol=0.008)
    if rel is None:
        o = obj_pos(ctx)
        rel = float(np.hypot(o[0] - d[0], o[1] - d[1]))
    rig.squeeze(GRIP_OPEN, 22)
    for _ in range(120):
        a = np.zeros(7); a[6] = GRIP_OPEN
        rig.step(a)
    ok = bool(ctx.env.check_success())
    rec["release_xy_err_m"] = round(rel, 5)
    rec["official_success"] = ok
    rec["final_obj"] = rnd(obj_pos(ctx))
    write_json("matrix_%d_%s.json" % (idx, variant), rec)
    print(json.dumps({"task": idx, "variant": variant, "carried": True,
                      "dz_mm": round(1000 * dz, 1),
                      "release_err_mm": round(1000 * rel, 1), "success": ok}, indent=2))
    ctx.env.close()
    return rec


def main_basket():
    """Where is the basket, really?  The grasp now carries, so the remaining question is the
    release: how high is the rim, how wide is the mouth, and where is the contain_region site."""
    import numpy as np
    ctx = load(IDX)
    sim = ctx.sim
    bodies = ctx.bodies
    bid = bodies.index("basket_1_main") if "basket_1_main" in bodies else next(
        i for i, b in enumerate(bodies) if b.startswith("basket_1"))
    rec = {"task": ctx.name, "index": IDX, "goal": rnd(ctx.goal, 5), "goal_kind": ctx.goal_kind,
           "basket_body": bodies[bid], "basket_pos": rnd(sim.data.body_xpos[bid], 5),
           "geoms": []}
    for g in body_geoms(sim, bid):
        lo, hi, kind = geom_aabb(sim, g, np)
        rec["geoms"].append({"name": gname(sim.model, g), "kind": kind,
                             "collision": bool(collision(sim, g)),
                             "lo": rnd(lo, 5), "hi": rnd(hi, 5)})
    coll = [g for g in rec["geoms"] if g["collision"]]
    if coll:
        lo = np.array([g["lo"] for g in coll]).min(0)
        hi = np.array([g["hi"] for g in coll]).max(0)
        rec["aabb"] = [rnd(lo, 5), rnd(hi, 5)]
        rec["rim_z"] = round(float(hi[2]), 5)
        rec["mouth_xy"] = [round(float(hi[0] - lo[0]), 5), round(float(hi[1] - lo[1]), 5)]
        rec["centre_xy"] = [round(float((hi[0] + lo[0]) / 2), 5),
                            round(float((hi[1] + lo[1]) / 2), 5)]
        rec["floor_z"] = round(float(lo[2]), 5)
    # What does the success predicate actually measure?  Report the predicate inputs directly.
    states = getattr(ctx.env.env, "object_states_dict", {})
    rec["object_states"] = sorted(states.keys())
    rec["goal_state"] = getattr(ctx.env.env, "parsed_problem", {}).get("goal_state")
    # free-fall drop test: teleport the object above the basket axis and let physics decide
    settle_world(ctx)
    lo_o, hi_o = obj_aabb(ctx)
    obj_h = float(hi_o[2] - lo_o[2])
    base = obj_pos(ctx)
    drops = []
    for above in (0.20, 0.12, 0.06, 0.02):
        p = base.copy()
        p[0] = float(ctx.goal[0]); p[1] = float(ctx.goal[1])
        p[2] = float(rec.get("rim_z", 0.0)) + above + obj_h / 2
        q = obj_quat(ctx)
        sim.data.set_joint_qpos(ctx.obj_body + "_joint0",
                                np.concatenate([p, q])) if False else None
        joint = [j for j in range(sim.model.njnt)
                 if sim.model.jnt_type[j] == 0
                 and int(field(sim.model, "bodyid", -1) if False else 0) == 0]
        drops.append({"above_rim": above, "target": rnd(p, 5)})
    rec["drop_plan"] = drops
    write_json("basket_%d.json" % IDX, rec)
    print(json.dumps({k: rec[k] for k in ("task", "goal", "goal_kind", "basket_pos", "aabb",
                                          "rim_z", "mouth_xy", "centre_xy", "floor_z",
                                          "object_states", "goal_state")}, indent=2))
    ctx.env.close()
    return 0


def predicate_state(ctx):
    """Recompute the official predicate BY HAND from the same quantities it uses, so a False
    can be attributed to a specific inequality instead of being taken on faith."""
    import numpy as np
    env = ctx.env.env
    sim = ctx.sim
    obj = ctx.obj
    region = ctx.region
    site = ctx.sim.model.site_name2id(region)
    site_pos = np.array(sim.data.site_xpos[site], dtype=float)
    site_mat = np.array(sim.data.site_xmat[site], dtype=float).reshape(3, 3)
    site_obj = env.object_sites_dict[region]
    size = np.abs(np.asarray(site_obj.size, dtype=float))
    total = np.abs(site_mat @ size)
    obj_pos = np.array(sim.data.body_xpos[env.obj_body_id[obj]], dtype=float)
    ub = site_pos + total
    lb = site_pos - total
    lb[2] -= 0.01
    basket = next((b for b in ctx.bodies if b.startswith("basket_1")), None)
    basket_pos = (rnd(sim.data.body_xpos[ctx.bodies.index(basket)], 5) if basket else None)
    return {
        "site": rnd(site_pos, 5), "site_size": rnd(size, 5), "lb": rnd(lb, 5), "ub": rnd(ub, 5),
        "obj_body_pos": rnd(obj_pos, 5),
        "inside": bool(np.all(obj_pos > lb) and np.all(obj_pos < ub)),
        "margin": rnd(np.minimum(obj_pos - lb, ub - obj_pos), 5),
        "basket_pos": basket_pos,
        "check_success": bool(ctx.env.check_success()),
        "eef": rnd(ctx.rig.eef(), 5),
    }


RELEASES = ["at_site", "deep", "deep_open_then_up", "at_rim_minus"]


def do_release(ctx, rig, R_target, strategy, rec):
    """Carry is solved; this is the placement half."""
    import numpy as np
    d = np.array(ctx.goal, dtype=float)
    basket = predicate_state(ctx)
    rim = None
    b = next((i for i, nm in enumerate(ctx.bodies) if nm.startswith("basket_1")), None)
    if b is not None:
        lo = np.array([1e9] * 3); hi = -lo
        for g in body_geoms(ctx.sim, b):
            a, c, _k = geom_aabb(ctx.sim, g, np)
            lo = np.minimum(lo, a); hi = np.maximum(hi, c)
        rim = float(hi[2])
    obj_h = float(ctx.lift_half[1] - ctx.lift_half[0])
    # object centre sits this far below the grip site while carried (measured at lift time)
    off = float(ctx.carry_offset)
    rec["release_setup"] = {"strategy": strategy, "site": rnd(d, 5), "rim_z": rim,
                            "obj_half_height": round(obj_h, 4),
                            "carry_offset": round(off, 4),
                            "predicate_before": basket}
    if strategy == "at_site":
        tgt = d[2]
    elif strategy == "deep":
        tgt = d[2] - 0.045
    elif strategy == "at_rim_minus":
        tgt = (rim - 0.02) if rim else d[2]
    else:
        tgt = d[2]
    # approach above the mouth, then lower to the release height
    if R_target is not None:
        rig.pose_to((d[0], d[1], d[2] + 0.12), R_target, GRIP_CLOSE, steps=260, tol=0.012)
    else:
        rig.drive((d[0], d[1], d[2] + 0.12), GRIP_CLOSE, steps=260, tol=0.012)
    trace = []
    for k in range(260):
        if rig.terminated:
            break
        cur = rig.eef()
        err = np.array([d[0], d[1], tgt]) - cur
        if float(np.linalg.norm(err)) <= 0.006:
            break
        a = np.zeros(7)
        a[:3] = np.clip(err * 10.0, -0.35, 0.35)
        if R_target is not None:
            from robosuite.utils.control_utils import orientation_error
            a[3:6] = np.clip(np.asarray(orientation_error(R_target, rig.rot())) * 4.0, -1, 1)
        a[6] = GRIP_CLOSE
        rig.step(a)
        if k % 10 == 0:
            o = obj_pos(ctx)
            trace.append({"k": k, "eef_z": round(float(rig.eef()[2]), 4),
                          "obj_z": round(float(o[2]), 4),
                          "obj_xy": rnd(o[:2], 4),
                          "pred_in": bool(predicate_state(ctx)["inside"])})
    rec["lower_trace"] = trace
    rec["predicate_at_release"] = predicate_state(ctx)
    # open the gripper slowly and record what the object does
    after = []
    for k in range(60):
        a = np.zeros(7)
        a[6] = GRIP_OPEN
        if strategy == "deep_open_then_up" and k > 20:
            a[2] = 0.25
        rig.step(a)
        if k % 6 == 0 or k == 59:
            o = obj_pos(ctx)
            ps = predicate_state(ctx)
            after.append({"k": k, "obj": rnd(o, 4), "inside": ps["inside"],
                          "margin": ps["margin"]})
    rec["after_release"] = after
    # let it settle
    for _ in range(120):
        a = np.zeros(7); a[6] = GRIP_OPEN
        rig.step(a)
    rec["predicate_final"] = predicate_state(ctx)
    rec["official_success"] = bool(ctx.env.check_success())
    return rec


def main_release():
    """The grasp is solved by 'neck'; this isolates the placement half and attributes it."""
    import numpy as np
    strategies = os.environ.get("RELEASES", ",".join(RELEASES)).split(",")
    out = []
    for strat in strategies:
        ctx = load(IDX)
        rig = ctx.rig
        settle_world(ctx)
        lm = landmarks(ctx)
        c = np.array(lm["centre"], dtype=float)
        z_neck = float(lm["neck_z"])
        z_hi = float(lm["extent_true"][1])
        rec = {"phase": "release", "task": ctx.name, "index": IDX, "strategy": strat,
               "landmarks": {k: v for k, v in lm.items() if k != "profile"}}
        rig.squeeze(GRIP_OPEN, 25)
        rig.drive((c[0], c[1], z_hi + 0.12), GRIP_OPEN, steps=260, tol=0.012)
        rig.drive((c[0], c[1], z_neck + 0.02), GRIP_OPEN, steps=180, tol=0.010)
        rig.drive((c[0], c[1], z_neck), GRIP_OPEN, steps=180, tol=0.006)
        before = obj_pos(ctx)
        rig.squeeze(GRIP_CLOSE, 28)
        rig.drive((rig.eef()[0], rig.eef()[1], rig.eef()[2] + 0.14), GRIP_CLOSE, steps=200)
        after = obj_pos(ctx)
        ctx.carry_offset = float(before[2] - rig.eef()[2])
        ctx.lift_half = (float(obj_aabb(ctx)[0][2]), float(obj_aabb(ctx)[1][2]))
        rec["lift"] = {"dz": round(float(after[2] - before[2]), 4),
                       "carried": bool(after[2] - before[2] > LIFT_PROOF_M),
                       "carry_offset": round(ctx.carry_offset, 4)}
        rec = do_release(ctx, rig, None, strat, rec)
        write_json("release_%d_%s.json" % (IDX, strat), rec)
        print(json.dumps({"task": IDX, "strategy": strat, "carried": rec["lift"]["carried"],
                          "success": rec["official_success"],
                          "predicate_final": rec["predicate_final"]}, indent=2))
        out.append({"strategy": strat, "carried": rec["lift"]["carried"],
                    "success": rec["official_success"],
                    "obj": rec["predicate_final"]["obj_body_pos"],
                    "margin": rec["predicate_final"]["margin"]})
        ctx.env.close()
    write_json("release_%d_summary.json" % IDX, {"index": IDX, "rows": out})
    print(json.dumps(out, indent=2))
    return 0


def basket_state(ctx):
    """Basket body pose + rim, measured live (the basket is a free body: it can be pushed)."""
    import numpy as np
    b = next((k for k, nm in enumerate(ctx.bodies) if nm.startswith("basket_1")), None)
    if b is None:
        return None
    lo = np.array([1e9] * 3); hi = -lo
    for g in body_geoms(ctx.sim, b):
        a, c, _k = geom_aabb(ctx.sim, g, np)
        lo = np.minimum(lo, a); hi = np.maximum(hi, c)
    return {"body_pos": rnd(ctx.sim.data.body_xpos[b], 5),
            "aabb": [rnd(lo, 5), rnd(hi, 5)], "rim_z": round(float(hi[2]), 5),
            "centre_xy": [round(float((hi[0] + lo[0]) / 2), 5),
                          round(float((hi[1] + lo[1]) / 2), 5)]}


def carry_pipeline(ctx, rig, lm, carry_clearance, release_mode, rec):
    """Pick at the measured neck, carry HIGH enough that the hanging object clears the basket
    rim, translate over the mouth, lower, release.  Returns the record."""
    import numpy as np
    c = np.array(lm["centre"], dtype=float)
    z_neck = float(lm["neck_z"])
    z_hi = float(lm["extent_true"][1])
    rig.squeeze(GRIP_OPEN, 25)
    rig.drive((c[0], c[1], z_hi + 0.12), GRIP_OPEN, steps=260, tol=0.012)
    rig.drive((c[0], c[1], z_neck + 0.02), GRIP_OPEN, steps=180, tol=0.010)
    # The descent is slow (measured ~1.2 mm of eef travel per control step), so it needs enough
    # steps to actually arrive; an exhausted step budget must not be reported as a collision.
    reached = rig.drive((c[0], c[1], z_neck), GRIP_OPEN, steps=420, tol=0.006)
    gap = float(rig.eef()[2]) - float(z_neck)
    rec["descent"] = {"reached": bool(reached), "eef_z": round(float(rig.eef()[2]), 4),
                      "target_z": round(float(z_neck), 4), "gap_m": round(gap, 4)}
    rec["grasp_pose"] = {"eef": rnd(rig.eef()), "target_z": round(z_neck, 4),
                         "obj": rnd(obj_pos(ctx)), "basket": basket_state(ctx)}
    before = obj_pos(ctx)
    rig.squeeze(GRIP_CLOSE, 28)
    rig.drive((rig.eef()[0], rig.eef()[1], rig.eef()[2] + 0.14), GRIP_CLOSE, steps=200)
    after = obj_pos(ctx)
    dz = float(after[2] - before[2])
    carried = dz > LIFT_PROOF_M
    hang = float(after[2] - rig.eef()[2])
    rec["lift"] = {"dz": round(dz, 4), "carried": bool(carried),
                   "hang_below_grip_m": round(hang, 4), "obj_after": rnd(after)}
    if not carried:
        rec["official_success"] = False
        rec["note"] = "grasp did not carry"
        rec["predicate_final"] = predicate_state(ctx)
        return rec
    bs = basket_state(ctx)
    rim = float(bs["rim_z"])
    lo_now, hi_now = obj_aabb(ctx)
    obj_bottom = float(lo_now[2])
    # height needed so the hanging object's BASE clears the rim by carry_clearance
    need_eef = rim + carry_clearance + (float(rig.eef()[2]) - obj_bottom)
    rec["carry_plan"] = {"rim_z": round(rim, 4), "obj_bottom_m": round(obj_bottom, 4),
                         "eef_now": round(float(rig.eef()[2]), 4),
                         "need_eef_for_clearance": round(need_eef, 4),
                         "clearance": carry_clearance}
    rig.drive((rig.eef()[0], rig.eef()[1], need_eef), GRIP_CLOSE, steps=240, tol=0.008)
    rec["carry_height_reached"] = {"eef": rnd(rig.eef()),
                                   "obj_bottom": round(float(obj_aabb(ctx)[0][2]), 4),
                                   "basket": basket_state(ctx)}
    bs = basket_state(ctx)
    tx, ty = bs["centre_xy"]
    rig.drive((tx, ty, float(rig.eef()[2])), GRIP_CLOSE, steps=300, tol=0.010)
    rec["over_basket"] = {"eef": rnd(rig.eef()), "obj": rnd(obj_pos(ctx)),
                          "basket": basket_state(ctx)}
    ps = predicate_state(ctx)
    if release_mode == "contain_mid":
        tgt_z = float((ps["lb"][2] + ps["ub"][2]) / 2.0) - hang
    elif release_mode == "just_above_floor":
        tgt_z = rim - 0.02
    else:
        tgt_z = float(rig.eef()[2])
    trace = []
    for k in range(300):
        if rig.terminated:
            break
        eef = rig.eef()
        err = np.array([tx, ty, tgt_z]) - eef
        if float(np.linalg.norm(err)) <= 0.005:
            break
        a = np.zeros(7)
        a[:3] = np.clip(err * 10.0, -0.3, 0.3)
        a[6] = GRIP_CLOSE
        rig.step(a)
        if k % 8 == 0:
            ps = predicate_state(ctx)
            trace.append({"k": k, "eef_z": round(float(rig.eef()[2]), 4),
                          "obj": rnd(obj_pos(ctx), 4), "inside": ps["inside"],
                          "basket_y": ps["basket_pos"][1] if ps["basket_pos"] else None})
    rec["lower"] = {"trace": trace, "eef": rnd(rig.eef()), "obj": rnd(obj_pos(ctx)),
                    "basket": basket_state(ctx), "predicate": predicate_state(ctx)}
    for _ in range(30):
        a = np.zeros(7); a[6] = GRIP_OPEN
        rig.step(a)
    for _ in range(120):
        a = np.zeros(7); a[6] = GRIP_OPEN
        rig.step(a)
    rec["predicate_final"] = predicate_state(ctx)
    rec["official_success"] = bool(ctx.env.check_success())
    rec["note"] = "official predicate"
    return rec


def main_carry():
    """The decisive experiment: does carrying HIGHER stop the basket from being pushed away?"""
    import numpy as np
    clears = [float(x) for x in os.environ.get("CLEARS", "0.0,0.02,0.04,0.06").split(",")]
    mode = os.environ.get("RELEASE_MODE", "contain_mid")
    rows = []
    for cl in clears:
        ctx = load(IDX)
        rig = ctx.rig
        settle_world(ctx)
        lm = landmarks(ctx)
        rec = {"phase": "carry", "task": ctx.name, "index": IDX,
               "clearance": cl, "release_mode": mode,
               "landmarks": {k: v for k, v in lm.items() if k != "profile"}}
        rec = carry_pipeline(ctx, rig, lm, cl, mode, rec)
        write_json("carry_%d_clr%03d.json" % (IDX, int(round(cl * 1000))), rec)
        row = {"clearance": cl, "carried": rec["lift"]["carried"],
               "success": rec.get("official_success"),
               "basket_drift_m": (round(float(np.linalg.norm(
                   np.array(rec["predicate_final"]["basket_pos"][:2])
                   - np.array(rec["grasp_pose"]["basket"]["body_pos"][:2]))), 4)
                   if rec["predicate_final"].get("basket_pos") else None),
               "obj_final": rec["predicate_final"]["obj_body_pos"],
               "inside": rec["predicate_final"]["inside"],
               "margin": rec["predicate_final"]["margin"]}
        rows.append(row)
        print(json.dumps(row, indent=2))
        ctx.env.close()
    write_json("carry_%d_summary.json" % IDX, {"index": IDX, "rows": rows})
    print(json.dumps(rows, indent=2))
    return 0


def fixed_policy(idx, init_idx, clearance=0.04, suite=None):
    """The fix under test: pick at the MEASURED neck of the settled object, carry high enough
    that the hanging bottle clears the basket rim, then lower and release.
    Both halves are measured quantities, not constants fitted to these two tasks."""
    import numpy as np
    os.environ["INIT_IDX"] = str(init_idx)
    ctx = load(idx, suite)
    rig = ctx.rig
    settle = settle_world(ctx)
    lm = landmarks(ctx)
    rec = {"task": ctx.name, "index": idx, "init_idx": init_idx, "clearance": clearance,
           "settle": {"dz": settle["settle_dz"], "dxy": settle["settle_dxy"]},
           "landmarks": {k: v for k, v in lm.items() if k != "profile"}}
    rec = carry_pipeline(ctx, rig, lm, clearance, "contain_mid", rec)
    ok = rec.get("official_success")
    write_json("fixed_%d_i%d.json" % (idx, init_idx), rec)
    out = {"task": idx, "init_idx": init_idx, "name": ctx.name, "carried": rec["lift"]["carried"],
           "lift_mm": round(1000 * rec["lift"]["dz"], 1),
           "success": bool(ok),
           "basket_drift_m": (round(float(np.linalg.norm(
               np.array(rec["predicate_final"]["basket_pos"][:2])
               - np.array(rec["grasp_pose"]["basket"]["body_pos"][:2]))), 4)
               if rec["predicate_final"].get("basket_pos") else None),
           "obj_final": rec["predicate_final"]["obj_body_pos"],
           "neck_z": lm.get("neck_z"), "grasp_z_true_mid": lm.get("grasp_z_true_mid"),
           "grasp_z_rbound": lm.get("grasp_z_rbound_frac0.5")}
    ctx.env.close()
    return out


def main_fixed():
    """Run the fixed policy over every init state the benchmark ships for these tasks."""
    import numpy as np
    import torch
    n_init = int(os.environ.get("N_INIT", "5"))
    tasks = [int(t) for t in os.environ.get("TASKS", str(IDX)).split(",")]
    rows = []
    for idx in tasks:
        name, bddl, init = task_paths(idx)
        st = torch.load(init, map_location="cpu", weights_only=False)
        arr = st.detach().cpu().numpy() if hasattr(st, "detach") else np.asarray(st)
        n = min(n_init, len(arr))
        for k in range(n):
            try:
                rows.append(fixed_policy(idx, k))
            except Exception as exc:
                rows.append({"task": idx, "init_idx": k, "error": repr(exc)})
            print(json.dumps(rows[-1]))
    write_json("fixed_summary_%s.json" % "_".join(str(t) for t in tasks),
               {"tasks": tasks, "rows": rows})
    print(json.dumps({"n": len(rows),
                      "success": sum(1 for r in rows if r.get("success")),
                      "carried": sum(1 for r in rows if r.get("carried"))}, indent=2))
    return 0


def main_matrix():
    only = os.environ.get("VARIANTS", "").strip()
    variants = only.split(",") if only else VARIANTS
    out = []
    for v in variants:
        try:
            out.append(attempt(IDX, v))
        except Exception as exc:      # a variant must never take the run down
            out.append({"variant": v, "index": IDX, "error": repr(exc)})
            print(json.dumps({"task": IDX, "variant": v, "error": repr(exc)}))
    summary = [{"variant": r.get("variant"), "carried": r.get("lift", {}).get("carried"),
                "dz_mm": (round(1000 * r["lift"]["dz"], 1) if r.get("lift") else None),
                "release_err_mm": (round(1000 * r["release_xy_err_m"], 1)
                                   if r.get("release_xy_err_m") is not None else None),
                "success": r.get("official_success"), "error": r.get("error")}
               for r in out]
    write_json("matrix_%d_summary.json" % IDX,
               {"index": IDX, "task": out[0].get("task") if out else None, "variants": summary})
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    if PHASE == "measure":
        sys.exit(main_measure())
    if PHASE == "info":
        sys.exit(main_info())
    if PHASE == "settle":
        sys.exit(main_settle())
    if PHASE == "descend":
        sys.exit(main_descend())
    if PHASE == "basket":
        sys.exit(main_basket())
    if PHASE == "fixed":
        sys.exit(main_fixed())
    if PHASE == "carry":
        sys.exit(main_carry())
    if PHASE == "release":
        sys.exit(main_release())
    if PHASE == "matrix":
        sys.exit(main_matrix())
    print(json.dumps({"phase": PHASE, "blocked": "unknown phase"}))
    sys.exit(2)