#!/usr/bin/env python3
"""How low can the arm actually go? Separates a reach limit from an obstacle.
"""
import os, sys, json
ROOT = "/mnt/c/Users/fuker/Desktop/workspace/ext-bench/LIBERO"
sys.path.insert(0, ROOT)


def main():
    import numpy as np, torch
    from libero.libero.envs import OffScreenRenderEnv
    bddl = os.path.join(ROOT, "libero/libero/bddl_files/libero_object",
                        "pick_up_the_alphabet_soup_and_place_it_in_the_basket.bddl")
    init = os.path.join(ROOT, "libero/libero/init_files/libero_object",
                        "pick_up_the_alphabet_soup_and_place_it_in_the_basket.pruned_init")
    env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=64, camera_widths=64)
    env.reset()
    st = torch.load(init, map_location="cpu", weights_only=False)
    env.set_init_state((st.detach().cpu().numpy() if hasattr(st, "detach") else st)[0])
    sim = env.env.sim
    site = sim.model.site_name2id("gripper0_grip_site")

    def eef():
        return np.array(sim.data.site_xpos[site], dtype=float)

    # free space: the middle of the table, away from the can and the basket
    free = np.array([0.05, 0.0, 0.02])
    best = 9.9
    tgz = []
    for i in range(300):
        cur = eef()
        err = free - cur
        a = np.zeros(7)
        a[:3] = np.clip(err * 18.0, -1.0, 1.0)
        a[6] = 1.0
        env.step(a)
        cur = eef()
        if cur[2] < best:
            best = float(cur[2])
        if i % 60 == 0:
            tgz.append([round(float(cur[0]), 3), round(float(cur[1]), 3),
                        round(float(cur[2]), 3)])
    obj = np.array(sim.data.body_xpos[list(sim.model.body_names).index("alphabet_soup_1_main")])
    print(json.dumps({
        "lowest_eef_z_in_free_space": round(best, 4),
        "target_z_requested": 0.02,
        "eef_trace": tgz,
        "object_origin_z": round(float(obj[2]), 4),
        "reading": ("reach limit" if best > 0.055 else "reach is fine - the can blocked it"),
    }, indent=2))
    env.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
