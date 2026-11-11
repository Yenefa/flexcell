#!/usr/bin/env python3
"""Run an OFFICIAL LIBERO task with the goal read from its own BDDL, not hardcoded.

WHY THIS IS THE TRANSFER TEST: the previous controller named alphabet_soup_1 and basket_1 by hand,
so passing told us nothing about a second task. Here the object and the goal region are parsed out
of the official goal clause, and the same phase policy runs unchanged. If it works on tasks it was
never written for, that is the first evidence of transfer rather than a one-off script.

Nothing about the environment or the predicate changes. Oracle perception is still declared.
"""
import json
import os
import re
import sys

ROOT = "/mnt/c/Users/fuker/Desktop/workspace/ext-bench/LIBERO"
sys.path.insert(0, ROOT)

SUITE = os.environ.get("LIBERO_SUITE", "libero_object")
IDX = int(os.environ.get("LIBERO_TASK", "0"))
OUT = os.environ.get("LIBERO_OUT", "/tmp/libero_transfer/result.json")

K_POS = 18.0
GRIP_OPEN = -1.0     # robosuite: +1 closes, -1 opens
GRIP_CLOSE = 1.0


def parse_goal(bddl_text):
    """Pull (object, region) pairs straight out of the official goal clause."""
    start = bddl_text.find("(:goal")
    chunk = bddl_text[start:]
    pairs = re.findall(r"\((?:On|In)\s+([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\)", chunk)
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
    bddl_text = open(bddl_path, encoding="utf-8").read()
    pairs = parse_goal(bddl_text)
    if not pairs:
        print(json.dumps({"task": name, "blocked": "no (On obj region) pair in the goal"}))
        return 2
    obj, region = pairs[0]

    env = OffScreenRenderEnv(bddl_file_name=bddl_path, camera_heights=64, camera_widths=64)
    env.reset()
    st = torch.load(init, map_location="cpu", weights_only=False)
    env.set_init_state((st.detach().cpu().numpy() if hasattr(st, "detach") else st)[0])
    sim = env.env.sim
    bodies = list(sim.model.body_names)
    sites = list(sim.model.site_names)
    log = []

    obj_body = obj + "_main"
    if obj_body not in bodies:
        obj_body = next((b for b in bodies if b.startswith(obj)), None)
    if region not in sites:
        print(json.dumps({"task": name, "blocked": "region site %s not found" % region,
                          "sites": [s for s in sites if "region" in s]}))
        return 3

    site = sim.model.site_name2id("gripper0_grip_site")

    def eef():
        return np.array(sim.data.site_xpos[site], dtype=float)

    def pos_body(n):
        return np.array(sim.data.body_xpos[bodies.index(n)], dtype=float)

    def pos_site(n):
        return np.array(sim.data.site_xpos[sim.model.site_name2id(n)], dtype=float)

    def drive(target, gripper, steps=260, tol=0.010, stop=None):
        for i in range(steps):
            cur = eef()
            err = np.asarray(target, float) - cur
            if float(np.linalg.norm(err)) <= tol or (stop is not None and stop(cur)):
                return True
            a = np.zeros(7)
            a[:3] = np.clip(err * K_POS, -1.0, 1.0)
            a[6] = gripper
            env.step(a)
        return False

    o = pos_body(obj_body)
    d = pos_site(region)
    log.append("parsed goal: %s -> %s" % (obj, region))
    log.append("object body %s at %s ; goal region at %s" % (
        obj_body, np.round(o, 3).tolist(), np.round(d, 3).tolist()))

    drive(o + np.array([0.0, 0.0, 0.12]), GRIP_OPEN)
    drive(np.array([o[0], o[1], o[2] + 0.02]), GRIP_OPEN, tol=0.008,
          stop=lambda c: (np.hypot(c[0] - o[0], c[1] - o[1]) < 0.012 and c[2] < o[2] + 0.06))
    for _ in range(20):
        a = np.zeros(7); a[6] = GRIP_CLOSE; env.step(a)
    drive(np.array([eef()[0], eef()[1], eef()[2] + 0.14]), GRIP_CLOSE)
    drive(np.array([d[0], d[1], d[2] + 0.10]), GRIP_CLOSE)
    drive(np.array([d[0], d[1], d[2] + 0.005]), GRIP_CLOSE, tol=0.02,
          stop=lambda c: (np.hypot(c[0] - d[0], c[1] - d[1]) < 0.015 and c[2] < d[2] + 0.04))
    carried = pos_body(obj_body)
    log.append("object while carried at %s" % np.round(carried, 3).tolist())
    for _ in range(20):
        a = np.zeros(7); a[6] = GRIP_OPEN; env.step(a)
    success_trace = []
    for k in range(120):
        a = np.zeros(7); a[6] = GRIP_OPEN; env.step(a)
        if k % 30 == 0:
            success_trace.append(bool(env.check_success()))
    tract = bool(env.check_success())
    log.append("success trace during settle: %s" % success_trace)
    log.append("object final at %s" % np.round(pos_body(obj_body), 3).tolist())

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"task": name, "suite": SUITE, "index": IDX,
                   "parsed_object": obj, "parsed_region": region,
                   "official_success": tract, "log": log,
                   "perception": "ORACLE (simulator state), not camera",
                   "policy": "same phase controller, targets parsed from the official goal"}, f,
                  indent=2)
    print(json.dumps({"task": name, "official_success": tract,
                      "parsed_goal": [obj, region]}, indent=2))
    env.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
