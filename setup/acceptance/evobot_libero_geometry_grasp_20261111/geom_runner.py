#!/usr/bin/env python3
"""Derive the grasp height from the object's own geometry instead of a hand-tuned offset.

WHY: the previous round transferred the goal parsing but failed two of three tasks, and both
failures were grasp failures - a +2 cm offset tuned on a can does not fit a flat box or a thin
bottle. The capability the task demanded is "measure the object and choose the grasp", so this
version measures the axis-aligned extent of the target body and aims at its middle.

This is still a scripted policy. What changes is where the number comes from: the object, not me.
"""
import json
import os
import re
import sys

ROOT = "/mnt/c/Users/fuker/Desktop/workspace/ext-bench/LIBERO"
sys.path.insert(0, ROOT)

SUITE = os.environ.get("LIBERO_SUITE", "libero_object")
IDX = int(os.environ.get("LIBERO_TASK", "0"))
OUT = os.environ.get("LIBERO_OUT", "/tmp/libero_geom/r.json")
FRAC = float(os.environ.get("GRASP_FRAC", "0.5"))

K_POS = 18.0
GRIP_OPEN = -1.0
GRIP_CLOSE = 1.0


def parse_goal(bddl_text):
    start = bddl_text.find("(:goal")
    pairs = re.findall(r"\((?:On|In)\s+([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\)", bddl_text[start:])
    return [(o, r) for o, r in pairs if r.endswith("_region")]


def main():
    import importlib.util
    import numpy as np
    import torch
    from libero.libero.envs import OffScreenRenderEnv

    tm_path = os.path.join(ROOT, "libero", "libero", "benchmark", "libero_suite_task_map.py")
    spec = importlib.util.spec_from_file_location("tm", tm_path)
    tm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tm)
    name = tm.libero_task_map[SUITE][IDX]
    bddl_path = os.path.join(ROOT, "libero", "libero", "bddl_files", SUITE, name + ".bddl")
    init = os.path.join(ROOT, "libero", "libero", "init_files", SUITE, name + ".pruned_init")
    pairs = parse_goal(open(bddl_path, encoding="utf-8").read())
    if not pairs:
        print(json.dumps({"task": name, "blocked": "no goal pair"}))
        return 2
    obj, region = pairs[0]

    env = OffScreenRenderEnv(bddl_file_name=bddl_path, camera_heights=64, camera_widths=64)
    env.reset()
    st = torch.load(init, map_location="cpu", weights_only=False)
    env.set_init_state((st.detach().cpu().numpy() if hasattr(st, "detach") else st)[0])
    sim = env.env.sim
    bodies = list(sim.model.body_names)
    sites = list(sim.model.site_names)
    obj_body = obj + "_main" if (obj + "_main") in bodies else next(
        (b for b in bodies if b.startswith(obj)), None)
    if region not in sites or obj_body is None:
        print(json.dumps({"task": name, "blocked": "body or region missing",
                          "obj_body": obj_body, "region": region}))
        return 3

    bid = bodies.index(obj_body)
    # axis-aligned extent of every geom belonging to the object body
    gids = [g for g in range(sim.model.ngeom) if sim.model.geom_bodyid[g] == bid]
    zs = []
    for g in gids:
        c = sim.data.geom_xpos[g]
        rb = float(sim.model.geom_rbound[g])
        zs.append((float(c[2]) - rb, float(c[2]) + rb))
    if not zs:
        print(json.dumps({"task": name, "blocked": "object body has no geoms"}))
        return 4
    z_lo = min(z[0] for z in zs)
    z_hi = max(z[1] for z in zs)
    centre = np.array(sim.data.body_xpos[bid], dtype=float)

    def grasp_z(frac):
        return z_lo + frac * (z_hi - z_lo)

    site = sim.model.site_name2id("gripper0_grip_site")

    def eef():
        return np.array(sim.data.site_xpos[site], dtype=float)

    def pos_body(n):
        return np.array(sim.data.body_xpos[bodies.index(n)], dtype=float)

    def pos_site(n):
        return np.array(sim.data.site_xpos[sim.model.site_name2id(n)], dtype=float)

    def drive(target, gripper, steps=260, tol=0.010, stop=None):
        for _ in range(steps):
            cur = eef()
            err = np.asarray(target, float) - cur
            if float(np.linalg.norm(err)) <= tol or (stop is not None and stop(cur)):
                return True
            a = np.zeros(7)
            a[:3] = np.clip(err * K_POS, -1.0, 1.0)
            a[6] = gripper
            env.step(a)
        return False

    d = pos_site(region)
    log = ["parsed goal %s -> %s" % (obj, region),
           "object extent z %.3f..%.3f -> grasp at %.3f (frac %.2f of the measured extent)" % (
               z_lo, z_hi, grasp_z(FRAC), FRAC)]
    target_grasp = np.array([centre[0], centre[1], grasp_z(0.5)])

    drive(np.array([centre[0], centre[1], z_hi + 0.12]), GRIP_OPEN)
    drive(target_grasp, GRIP_OPEN, tol=0.008,
          stop=lambda c: (np.hypot(c[0] - centre[0], c[1] - centre[1]) < 0.012
                          and c[2] < grasp_z(0.75)))
    z_at = float(eef()[2])
    log.append("descended to eef z %.3f (target %.3f)" % (z_at, grasp_z(0.5)))
    for _ in range(22):
        a = np.zeros(7); a[6] = GRIP_CLOSE; env.step(a)
    lifted = pos_body(obj_body) - centre
    log.append("object displacement after close+lift prep: %s" % np.round(lifted, 4).tolist())
    drive(np.array([eef()[0], eef()[1], eef()[2] + 0.14]), GRIP_CLOSE)
    carried = pos_body(obj_body)
    log.append("object while carried at %s" % np.round(carried, 3).tolist())
    drive(np.array([d[0], d[1], d[2] + 0.10]), GRIP_CLOSE)
    drive(np.array([d[0], d[1], d[2] + 0.005]), GRIP_CLOSE, tol=0.02,
          stop=lambda c: (np.hypot(c[0] - d[0], c[1] - d[1]) < 0.015 and c[2] < d[2] + 0.04))
    for _ in range(20):
        a = np.zeros(7); a[6] = GRIP_OPEN; env.step(a)
    trace = []
    for k in range(120):
        a = np.zeros(7); a[6] = GRIP_OPEN; env.step(a)
        if k % 30 == 0:
            trace.append(bool(env.check_success()))
    ok = bool(env.check_success())
    log.append("success trace: %s" % trace)
    log.append("object final at %s" % np.round(pos_body(obj_body), 3).tolist())

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"task": name, "index": IDX, "official_success": ok,
               "object_extent_z": [round(z_lo, 4), round(z_hi, 4)],
               "grasp_z": round(grasp_z(FRAC), 4), "log": log,
               "perception": "ORACLE", "policy": "grasp height from measured extent"},
              open(OUT, "w"), indent=2)
    print(json.dumps({"task": name, "official_success": ok,
                      "extent_z": [round(z_lo, 3), round(z_hi, 3)],
                      "grasp_z": round(grasp_z(FRAC), 3)}, indent=2))
    env.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
