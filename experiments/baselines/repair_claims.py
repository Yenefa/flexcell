#!/usr/bin/env python3
"""Repair the claim for archived runs where the self-assessment step failed.

WHY THIS IS NOT A SHORTCUT: the robot work is already done and archived (sim logs, ground
truth, observations). Only two steps failed - the assessor and the claim-carrying re-grade -
and both are pure post-processing. Re-running the robot would change the world, not the
answer.

Run as root: the sealed answers are needed for grading.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[2]
BASE = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/evobot-pair48")
PUBNAME = sys.argv[2] if len(sys.argv) > 2 else "recovery_public48"
ZONES = ('{"zone_1":[0.12,-0.15,0.0175],"zone_2":[0.25,0.05,0.0175]}')


def main():
    # sudo resets HOME to /root, so "~" is the wrong place to look under privilege.
    gate = "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/ci-public-window/scripts/evobot_llm_key.sh"
    if os.environ.get("FLEXCELL_KEY_FILE"):
        key = Path(os.environ["FLEXCELL_KEY_FILE"]).read_text().strip()
    else:
        key = subprocess.run(["bash", gate], check=True,
                             capture_output=True, text=True).stdout.strip()
    fixed = failed = 0
    for d in sorted(BASE.glob("HO-*")):
        pub = WT / "benchmark" / "held_out" / PUBNAME / (d.name + ".json")
        gt = d / "ground_truth.json"
        if not (pub.exists() and gt.exists() and (d / "sim").is_dir()):
            print("skip", d.name)
            failed += 1
            continue
        task = json.loads(pub.read_text(encoding="utf-8"))
        names = [o["name"] for o in task["objects"]]

        # 1. self-assessment. The budget is escalated by the caller for runs that still
        #    return empty content: this reasoning model spends the whole budget thinking.
        env = dict(os.environ, FLEXCELL_PILOT_API_KEY=key,
                   FLEXCELL_PILOT_MAX_TOKENS=os.environ.get("ASSESS_MAX_TOKENS",
                                                                  "16384"))
        r = subprocess.run(
            [sys.executable, str(WT / "runtime" / "verifier" / "self_assess.py"),
             "--run", str(d), "--spec", str(pub),
             "--out", str(d / "self_assessment.json")],
            cwd=str(WT), env=env, capture_output=True, text=True)
        sa = d / "self_assessment.json"
        if not sa.exists():
            (d / "self_assess_failed.txt").write_text(
                (r.stdout or "") + (r.stderr or "")[-1500:], encoding="utf-8")
            print("assess failed", d.name)
            failed += 1
            continue
        claim = "true" if json.loads(sa.read_text(encoding="utf-8"))["success"] else "false"

        # 2. rebuild the observation WITH the claim, then re-grade through sealed_evaluate
        obs = d / "observation_claimed.json"
        subprocess.run(
            [sys.executable, str(WT / "benchmark" / "evaluators" / "observe_from_run.py"),
             str(d / "sim"), str(obs), *names,
             "--ground-truth", str(gt), "--agent-claim", claim, "--zones", ZONES],
            cwd=str(WT), capture_output=True, text=True, check=True)
        subprocess.run(
            [sys.executable, str(WT / "benchmark" / "evaluators" / "sealed_evaluate.py"),
             "--public", str(pub), "--observation", str(obs),
             "--out", str(d / "verdict.json")],
            cwd=str(WT), capture_output=True, text=True, check=True)
        fixed += 1
    print()
    print("repaired:", fixed, "failed:", failed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
