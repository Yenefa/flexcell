"""Compare the ACTUAL archived plans of Baseline A-prime and Baseline B.

Re-planning would be the wrong method twice over: it would use a planner the A-v2 run
did not use, and it would answer a question about a hypothetical run instead of the one
that actually happened. Both arms recorded their plans, so the comparison reads those.

  A-prime  ci-public-window/evidence/baseline_a_v2_gated_20261111/<task>/plan.json
  B        setup/acceptance/evobot_baseline_b_v2_20261111/plans/<task>/plan.json

Both are in RunComposite vocabulary: stages carry an object_name and an absolute
place_pose. Two plans are compared as the ordered list of (object, place pose) pairs,
rounded to the millimetre the simulator actually resolves. Nothing is normalised toward
either arm.
"""
import glob
import json
import os

WT = "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp"
CI = "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/ci-public-window/evidence"
A_DIR = os.path.join(CI, "baseline_a_v2_gated_20261111")
B_DIR = os.path.join(WT, "setup/acceptance/evobot_baseline_b_v2_20261111/plans")
ROUND = 3


def signature(plan_path):
    plan = json.load(open(plan_path))
    stages = plan.get("stages") or []
    sig = []
    for st in stages:
        pose = st["place_pose"]
        sig.append((st["object_name"],
                    tuple(round(float(v), ROUND) for v in pose[:3])))
    return sig


def main():
    # The task id is the DIRECTORY name; basename is always "plan.json".
    tasks = sorted(os.path.basename(os.path.dirname(p))
                   for p in glob.glob(os.path.join(B_DIR, "*", "plan.json")))
    identical = different = missing = 0
    rows = []
    for task in tasks:
        a_path = os.path.join(A_DIR, task, "plan.json")
        b_path = os.path.join(B_DIR, task, "plan.json")
        if not os.path.exists(a_path):
            missing += 1
            rows.append((task, "NO_A_PLAN", "", ""))
            continue
        a, b = signature(a_path), signature(b_path)
        if a == b:
            identical += 1
            rows.append((task, "IDENTICAL", "", ""))
        else:
            different += 1
            rows.append((task, "DIFFERENT", str(a), str(b)))
    print("%-24s %-11s" % ("instance", "verdict"))
    for task, verdict, a, b in rows:
        print("%-24s %-11s" % (task, verdict))
        if verdict == "DIFFERENT":
            print("    A-prime: %s" % a)
            print("    B      : %s" % b)
    print()
    print("identical=%d  different=%d  no_A_plan=%d  total=%d"
          % (identical, different, missing, len(tasks)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())