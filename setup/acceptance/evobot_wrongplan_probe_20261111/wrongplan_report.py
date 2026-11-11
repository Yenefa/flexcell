#!/usr/bin/env python3
"""Print what the wrong plan did, what the evaluator said, and what the claim check would say."""
import json
import os
import sys

WT = "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp"
sys.path.insert(0, os.path.join(WT, "runtime", "verifier"))
import claim as C

ZONES = [{"name": "zone_1", "position": [0.12, -0.15, 0.0175], "radius": 0.06},
         {"name": "zone_2", "position": [0.25, 0.05, 0.0175], "radius": 0.06}]


def main():
    d = sys.argv[1]
    plan = json.load(open(os.path.join(d, "plan.json"), encoding="utf-8"))
    gt = json.load(open(os.path.join(d, "ground_truth.json"), encoding="utf-8"))
    v = json.load(open(os.path.join(d, "verdict.json"), encoding="utf-8"))
    print("  plan targets  :", [(s["object_name"], [round(x, 3) for x in s["place_pose"]])
                                for s in plan["stages"]])
    print("  measured world:", {k: [round(x[0], 3), round(x[1], 3)]
                                for k, x in gt["objects"].items()})
    print("  EVALUATOR     : passed=%s failed=%s" % (v["passed"], v.get("failed_clauses")))
    verdict, detail = C.check(plan, gt.get("objects") or {}, ZONES)
    print("  CLAIM CHECK   :", verdict)
    for st in detail.get("stages", []):
        print("    ", st["object"], st.get("zone"), "ok=", st.get("ok"))
    if "why" in detail:
        print("     why:", detail["why"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
