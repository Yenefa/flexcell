#!/usr/bin/env python3
"""Where does the official goal actually point? Print every region-ish site and its position."""
import json, os, sys
ROOT = "/mnt/c/Users/fuker/Desktop/workspace/ext-bench/LIBERO"
sys.path.insert(0, ROOT)
BDDL = os.path.join(ROOT, "libero/libero/bddl_files/libero_object",
                    "pick_up_the_alphabet_soup_and_place_it_in_the_basket.bddl")
INIT = os.path.join(ROOT, "libero/libero/init_files/libero_object",
                    "pick_up_the_alphabet_soup_and_place_it_in_the_basket.pruned_init")


def main():
    import numpy as np, torch
    from libero.libero.envs import OffScreenRenderEnv
    env = OffScreenRenderEnv(bddl_file_name=BDDL, camera_heights=64, camera_widths=64)
    env.reset()
    st = torch.load(INIT, map_location="cpu", weights_only=False)
    env.set_init_state((st.detach().cpu().numpy() if hasattr(st, "detach") else st)[0])
    sim = env.env.sim
    out = {}
    sites = list(sim.model.site_names)
    keep = [n for n in sites if any(k in n.lower() for k in ("contain", "basket", "soup", "region"))]
    out["region_sites"] = {n: np.round(sim.data.site_xpos[sim.model.site_name2id(n)], 4).tolist()
                           for n in keep}
    out["n_sites"] = len(sites)
    # what the env thinks the goal is
    for attr in ("goal", "reward", "_success"):
        pass
    try:
        out["goal"] = str(env.env._check_success.__doc__)[:120]
    except Exception:
        pass
    # list every object's region-facing info
    out["objects"] = {}
    for o in env.env.objects:
        try:
            out["objects"][o.name] = {
                "root_body": o.root_body,
                "joints": [j.name for j in o.joints][:4],
            }
        except Exception as e:
            out["objects"][o.name] = str(e)[:60]
    print(json.dumps(out, indent=2)[:2500])
    env.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
