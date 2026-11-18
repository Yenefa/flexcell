#!/usr/bin/env python3
# Read the REAL with/without comparison for closed-loop push recovery.
# WHY: unrouted.probe_push_recovery concluded "this archive cannot measure the effect"
# because it replayed attempts the policy under test produced itself - a selection effect.
# True of the path it reads, but it MISSED a separate, independently collected comparison
# in evobot_push_feedback_20261112: an A/B batch, same world/task/validator, preregistered
# order A1 B1 B2 A2 A3 B3, per-run evidence. NOT a replay.
# HONEST LIMITS: n=3 per arm, one exposed dev instance, does NOT isolate one component.
import json
import os

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BATCH = os.path.join(WT, "setup", "acceptance", "evobot_push_feedback_20261112")


def measure(acceptance=None):
    # Accept EITHER the batch directory itself OR its parent setup/acceptance. The first
    # version took only the latter's child and reported "not present" when handed the
    # parent, which silently turned a real comparison into a missing one.
    base = acceptance or BATCH
    batch = base
    if not os.path.exists(os.path.join(base, "result_summary.json")):
        batch = os.path.join(base, "evobot_push_feedback_20261112")
    path = os.path.join(batch, "result_summary.json")
    if not os.path.exists(path):
        return {"measured": False, "why": "result_summary.json not present"}
    try:
        data = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"measured": False, "why": "unreadable: " + str(exc)}
    fixed = data.get("fixed_batch") or {}
    control = fixed.get("control") or {}
    feedback = fixed.get("feedback") or {}
    c_pass = control.get("complete_task_passes")
    f_pass = feedback.get("complete_task_passes")
    c_runs = control.get("valid_runs")
    f_runs = feedback.get("valid_runs")
    same_world = bool(data.get("world_sha256"))
    claim = ("control %s/%s -> feedback %s/%s full task passes on ONE dev instance; "
             "same world/task/validator, preregistered order A1 B1 B2 A2 A3 B3. "
             "n=3 per arm; does NOT isolate one component; no generalization claim"
             % (c_pass, c_runs, f_pass, f_runs))
    return {
        "measured": all(isinstance(v, int) for v in (c_pass, f_pass, c_runs, f_runs)),
        "control_passes": c_pass, "control_runs": c_runs,
        "feedback_passes": f_pass, "feedback_runs": f_runs,
        "same_world_sha256": same_world,
        "pilots_separate": data.get("pilots_separate"),
        "is_real_comparison": (same_world and data.get("pilots_separate") is True),
        "claim": claim,
        "honest_limits": ["n=3 per arm", "one exposed dev instance",
                          "comparison does not isolate a single component",
                          "no unseen instance", "no statistical superiority"],
    }


if __name__ == "__main__":
    print(json.dumps(measure(), indent=2, ensure_ascii=False))
