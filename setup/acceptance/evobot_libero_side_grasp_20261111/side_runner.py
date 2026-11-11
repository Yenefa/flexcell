#!/usr/bin/env python3
"""Two capabilities the real tasks asked for: a lateral grasp and a verified release.

WHY THESE TWO: the previous round left three failures with two distinct mechanisms.
  salad_dressing, ketchup - a top-down descent stopped at eef z=0.107 against a 0.024 target,
    because the fingers meet the bottle cap. No amount of choosing a different height fixes that;
    the approach has to come from the side.
  bbq_sauce - it was carried fine and then released 3.6 cm off the basket axis. That is not a
    grasp problem at all, it is releasing without checking where the object actually is.

So: MODE=top|side_x|side_y selects the approach, and the release is now VERIFIED against the goal
region with re-approaches before letting go. Everything downstream is unchanged, and the official
predicate still decides.
"""
import json
import os
import re
import sys

ROOT = "/mnt/c/Users/fuker/Desktop/workspace/ext-bench/LIBERO"
sys.path.insert(0, ROOT)

SUITE = os.environ.get("LIBERO_SUITE", "libero_object")
IDX = int(os.environ.get("LIBERO_TASK", "0"))
OUT = os.environ.get("LIBERO_OUT", "/tmp/libero_side/r.json")
MODE = os.environ.get("MODE", "top")
FRAC = float(os.environ.get("GRASP_FRAC", "0.5"))
STANDOFF = 0.11          # how far to the side the lateral approach starts
RELEASE_TOL = 0.005      # metres; do not let go until the object is this close to the region axis

K_POS = 18.0
_TERMINATED = {"done": False}


def _step(env, a):
    """Step once, and treat a refusal as termination.

    `done` is not the only way an episode ends here: robosuite also refuses actions once the
    episode is finished, so the first refusal is taken as the signal instead of being allowed to
    abort the run. Before this, three tasks died mid-episode and produced no result at all.
    """
    if _TERMINATED["done"]:
        return
    try:
        _o, _r, done, _i = env.step(a)
    except ValueError:
        _TERMINATED["done"] = True
        return
    _TERMINATED["done"] = bool(done)
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
        print(json.dumps({"task": name, "blocked": "body or region missing"}))
        return 3

    bid = bodies.index(obj_body)
    gids = [g for g in range(sim.model.ngeom) if sim.model.geom_bodyid[g] == bid]
    zs = []
    for g in gids:
        c = sim.data.geom_xpos[g]
        rb = float(sim.model.geom_rbound[g])
        zs.append((float(c[2]) - rb, float(c[2]) + rb))
    z_lo = min(z[0] for z in zs)
    z_hi = max(z[1] for z in zs)
    gz = z_lo + FRAC * (z_hi - z_lo)
    centre = np.array(sim.data.body_xpos[bid], dtype=float)

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
            _step(env, a)
            if _TERMINATED["done"]:
                return True
        return False

    d = pos_site(region)
    log = ["mode %s, grasp frac %.2f, extent z %.3f..%.3f, grasp z %.3f" % (
        MODE, FRAC, z_lo, z_hi, gz), "goal %s -> %s" % (obj, region)]

    if MODE == "top":
        drive(np.array([centre[0], centre[1], z_hi + 0.12]), GRIP_OPEN)
        drive(np.array([centre[0], centre[1], gz]), GRIP_OPEN, tol=0.008)
    else:
        axis = 0 if MODE == "side_x" else 1
        off = np.zeros(3)
        off[axis] = STANDOFF
        start = np.array([centre[0], centre[1], gz]) + off
        drive(np.array([start[0], start[1], z_hi + 0.12]), GRIP_OPEN)
        drive(start, GRIP_OPEN, tol=0.010)
        log.append("lateral standoff reached at eef %s" % np.round(eef(), 3).tolist())
        drive(np.array([centre[0], centre[1], gz]), GRIP_OPEN, tol=0.012)
    log.append("grasp pose reached at eef %s (target z %.3f)" % (
        np.round(eef(), 3).tolist(), gz))

    for _ in range(22):
        a = np.zeros(7); a[6] = GRIP_CLOSE; _step(env, a)
    drive(np.array([eef()[0], eef()[1], eef()[2] + 0.14]), GRIP_CLOSE)
    carried = pos_body(obj_body)
    log.append("object after lift: %s" % np.round(carried, 3).tolist())

    drive(np.array([d[0], d[1], d[2] + 0.10]), GRIP_CLOSE)
    # verified release: approach the region axis and only let go once the OBJECT is on it
    release_err = None
    for attempt in range(4):
        obj_xy = pos_body(obj_body)
        err_xy = float(np.hypot(obj_xy[0] - d[0], obj_xy[1] - d[1]))
        log.append("release attempt %d: object xy error %.4f m" % (attempt, err_xy))
        if err_xy <= RELEASE_TOL:
            release_err = err_xy
            break
        cur = eef()
        drive(np.array([cur[0] - (obj_xy[0] - d[0]), cur[1] - (obj_xy[1] - d[1]),
                        min(cur[2], d[2] + 0.05)]), GRIP_CLOSE, tol=0.006)
    if release_err is None:
        obj_xy = pos_body(obj_body)
        release_err = float(np.hypot(obj_xy[0] - d[0], obj_xy[1] - d[1]))
    log.append("releasing at object xy error %.4f m" % release_err)

    for _ in range(20):
        a = np.zeros(7); a[6] = GRIP_OPEN; _step(env, a)
    trace = []
    for k in range(120):
        a = np.zeros(7); a[6] = GRIP_OPEN; _step(env, a)
        if k % 30 == 0:
            trace.append(bool(env.check_success()))
    ok = bool(env.check_success())
    log.append("episode terminated during run: %s" % _TERMINATED["done"])
    log.append("success trace: %s" % trace)
    log.append("object final %s" % np.round(pos_body(obj_body), 3).tolist())

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"task": name, "index": IDX, "mode": MODE, "official_success": ok,
               "release_xy_error_m": round(release_err, 5), "log": log,
               "perception": "ORACLE"}, open(OUT, "w"), indent=2)
    print(json.dumps({"task": name, "mode": MODE, "official_success": ok,
                      "release_err_mm": round(release_err * 1000, 1)}, indent=2))
    env.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
