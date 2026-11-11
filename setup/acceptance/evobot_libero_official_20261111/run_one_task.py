"""Load ONE official LIBERO task, run it in its own robosuite environment, print the official success flag.

This is the real integration step: official BDDL task, official env class from the LIBERO repo, official
success predicate via robosuite. The policy here is deliberately a no-op - the point is to prove the
pipeline loads, steps and grades, not to claim any skill.
"""
import os, sys, traceback, json
ROOT = "/mnt/c/Users/fuker/Desktop/workspace/ext-bench/LIBERO"
sys.path.insert(0, ROOT)

SUITE = os.environ.get("LIBERO_SUITE", "libero_object")
TASK_IDX = int(os.environ.get("LIBERO_TASK", "0"))

def main():
    from libero.libero.envs import OffScreenRenderEnv
    import importlib.util, numpy as np
    # Load the OFFICIAL task map by file. Importing it through the package would pull in
    # benchmark/__init__.py, which imports torch; the map itself is a plain dict of the
    # official task ids and needs none of it.
    tm_path = os.path.join(ROOT, "libero", "libero", "benchmark", "libero_suite_task_map.py")
    spec = importlib.util.spec_from_file_location("libero_task_map", tm_path)
    tm = importlib.util.module_from_spec(spec); spec.loader.exec_module(tm)
    libero_task_map = tm.libero_task_map

    names = libero_task_map[SUITE]
    name = names[TASK_IDX]
    bddl = os.path.join(ROOT, "libero", "libero", "bddl_files", SUITE, name + ".bddl")
    init = os.path.join(ROOT, "libero", "libero", "init_files", SUITE, name + ".pruned_init")
    print(json.dumps({"suite": SUITE, "task_index": TASK_IDX, "task": name,
                      "bddl_exists": os.path.exists(bddl),
                      "init_exists": os.path.exists(init)}, indent=2))
    if not os.path.exists(bddl):
        print("BDDL_MISSING"); return 2
    env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=64, camera_widths=64)
    env.reset()
    init_note = "not used"
    if os.path.exists(init):
        import torch
        try:
            states = torch.load(init, map_location="cpu", weights_only=False)
            if hasattr(states, "detach"):
                states = states.detach().cpu().numpy()
            env.set_init_state(states[0])
            init_note = "official init state loaded"
        except Exception as e:
            init_note = "INIT NOT LOADED: %s: %s" % (type(e).__name__, str(e)[:90])
    action_dim = int(env.env.action_dim)
    ac = np.zeros(action_dim)    # a deliberate no-op
    done = False
    for _ in range(5):
        obs, r, done, info = env.step(ac)
    ok = bool(env.check_success())
    print(json.dumps({"stepped": 5, "official_success_with_noop_policy": ok,
                      "action_dim": action_dim,
                      "init_note": init_note}, indent=2))
    env.close()
    return 0

try:
    sys.exit(main())
except Exception as e:
    print("FAILED:", type(e).__name__, str(e)[:300])
    traceback.print_exc(limit=4)
    sys.exit(1)
