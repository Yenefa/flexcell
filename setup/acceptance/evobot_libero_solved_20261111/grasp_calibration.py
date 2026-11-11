#!/usr/bin/env python3
"""Calibrate the grasp height by MEASURING whether the object is actually carried.

WHY NOT JUST TUNE BY HAND: the previous run showed the fingers stopping at z = 0.08 and the object
never leaving its start pose. Guessing the next height would be another guess. This sweeps the
descend target, closes, lifts, and records the object's displacement, so the height is chosen from
evidence. The task itself is untouched - the official environment and predicate decide everything.
"""
import json
import os
import sys

ROOT = "/mnt/c/Users/fuker/Desktop/workspace/ext-bench/LIBERO"
sys.path.insert(0, ROOT)
OUT = "/tmp/libero_calib/calib.json"

BDDL = os.path.join(ROOT, "libero/libero/bddl_files/libero_object",
                    "pick_up_the_alphabet_soup_and_place_it_in_the_basket.bddl")
INIT = os.path.join(ROOT, "libero/libero/init_files/libero_object",
                    "pick_up_the_alphabet_soup_and_place_it_in_the_basket.pruned_init")


def trial(descend_z_target, k=18.0, close_steps=20, lift_dz=0.12, close_gripper=True):
    import numpy as np
    import torch
    from libero.libero.envs import OffScreenRenderEnv
    env = OffScreenRenderEnv(bddl_file_name=BDDL, camera_heights=64, camera_widths=64)
    env.reset()
    st = torch.load(INIT, map_location="cpu", weights_only=False)
    env.set_init_state((st.detach().cpu().numpy() if hasattr(st, "detach") else st)[0])
    sim = env.env.sim
    bodies = list(sim.model.body_names)
    site = sim.model.site_name2id("gripper0_grip_site")

    def eef():
        return np.array(sim.data.site_xpos[site], dtype=float)

    def obj():
        return np.array(sim.data.body_xpos[bodies.index("alphabet_soup_1_main")], dtype=float)

    start = obj().copy()

    def drive(target, gripper, steps=240, tol=0.008):
        for _ in range(steps):
            err = np.asarray(target, float) - eef()
            if float(np.linalg.norm(err)) <= tol:
                return True
            a = np.zeros(7)
            a[:3] = np.clip(err * k, -1.0, 1.0)
            a[6] = gripper
            env.step(a)
        return False

    o = obj()
    drive(o + np.array([0.0, 0.0, 0.12]), -1.0)   # -1 opens
    z_here = float(eef()[2])
    reached = drive(np.array([o[0], o[1], descend_z_target]), -1.0, steps=240, tol=0.006)
    z_low = float(eef()[2])
    for _ in range(close_steps):
        a = np.zeros(7); a[6] = (1.0 if close_gripper else -1.0); env.step(a)
    lift_target = np.array([eef()[0], eef()[1], eef()[2] + lift_dz])
    drive(lift_target, 1.0, steps=200, tol=0.01)   # +1 holds closed
    carried = obj() - start
    res = {"descend_target": descend_z_target, "reached_target": bool(reached),
           "eef_z_before_descend": round(z_here, 4), "eef_z_after_descend": round(z_low, 4),
           "object_dz": round(float(carried[2]), 4),
           "object_shift_xy": round(float((carried[0] ** 2 + carried[1] ** 2) ** 0.5), 4),
           "gripper_closed": close_gripper}
    env.close()
    return res


def main():
    rows = []
    # CONTROL FIRST: descend and lift with the gripper left OPEN. Whatever displacement this
    # shows is settlement, not grasping, and every other row is judged against it. The first
    # sweep reported the SAME dz at every height, which was this artefact, not a grasp.
    control = trial(0.06, close_gripper=False)
    baseline_dz = control.get("object_dz", 0.0)
    print("CONTROL (gripper open):", json.dumps(control))
    for z in (0.02, 0.04, 0.06, 0.08, 0.10):
        try:
            r = trial(z)
            r["lift_above_control"] = round(r.get("object_dz", 0.0) - baseline_dz, 4)
            r["carried"] = bool(r["lift_above_control"] > 0.03)
        except Exception as e:
            r = {"descend_target": z, "error": "%s: %s" % (type(e).__name__, str(e)[:80])}
        rows.append(r)
        print(json.dumps(r))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(rows, open(OUT, "w"), indent=2)
    good = [r for r in rows if r.get("carried")]
    print()
    print("heights that actually lifted the object:", [r["descend_target"] for r in good])
    return 0


if __name__ == "__main__":
    sys.exit(main())
