#!/usr/bin/env python3
"""EvoBot Level 3 Recover: bounded, pre-registered failure handling.

DESIGN RULES (experiment protocol):
  - Recovery actions are declared BEFORE any run, in a fixed table. No strategy is
    invented after seeing a result.
  - The budget is bounded (one retry by default).
  - Recovery NEVER touches the evaluator, a tolerance, a threshold, or a world hash.
    It may only re-plan DESTINATIONS inside the existing bin radius, or re-dispatch.
  - The original failure record is kept. A recovery that succeeds does not delete the
    evidence that the first attempt failed.

This module DECIDES and RECORDS; it does not execute. Execution is the runner's job,
so the decision can be audited independently of whether it worked.
"""
import json
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WT / "evolution" / "diagnosis"))
sys.path.insert(0, str(WT / "experiments" / "baselines"))
import classify as diagnosis
import spread_destinations as sd

MAX_RETRIES = 1

# Fixed, pre-registered mapping: failure class -> bounded action.
# Nothing here changes grading. "respread" only enlarges spacing BETWEEN destinations
# of stages that share a bin, staying inside the declared bin radius.
ACTION_TABLE = {
    "planning": "respread",
    "runtime": "redispatch",
    "kinematics": "redispatch",
    "grasp": "redispatch",
    "perception": "reobserve",
    "tooling": "redispatch",
    "UNKNOWN": "no_recovery",
    "model": "no_recovery",
    "environment": "no_recovery",
    "state": "reobserve",
    "control": "no_recovery",
}

PROTECTED_TOPICS = ["evaluator", "tolerance", "threshold", "acceptance", "verifier"]


def decide(evidence, attempt=1):
    """Return a recovery decision dict. Pure function of the measured evidence."""
    cls, reason = diagnosis.classify(evidence)
    if attempt > MAX_RETRIES:
        return {"action": "no_recovery", "failure_class": cls,
                "reason": "retry budget exhausted", "measured_reason": reason}
    action = ACTION_TABLE.get(cls, "no_recovery")
    return {"action": action, "failure_class": cls, "measured_reason": reason,
            "attempt": attempt, "budget": MAX_RETRIES}


def apply_respread(plan, spread_step=0.060, bin_radius=0.06):
    """Widen spacing for same-bin stages. Never changes zones or grading.

    Returns a NEW plan dict. Raises ValueError if the widened positions would leave the
    declared bin radius - a recovery must not quietly break the task geometry.
    """
    stages = [dict(s, place_pose=list(s["place_pose"])) for s in plan["stages"]]
    # temporarily use a wider step by delegating to a local spread
    groups = {}
    for i, s in enumerate(stages):
        key = tuple(round(float(v), 5) for v in s["place_pose"])
        groups.setdefault(key, []).append(i)
    import math
    for key, idxs in groups.items():
        if len(idxs) < 2:
            continue
        for rank, i in enumerate(idxs):
            offset = (rank - (len(idxs) - 1) / 2.0) * spread_step
            cand = [key[0] + offset, key[1], key[2]]
            if math.hypot(cand[0] - key[0], cand[1] - key[1]) > bin_radius:
                raise ValueError("respread would leave the %.3f m bin" % bin_radius)
            stages[i]["place_pose"] = cand
            stages[i]["recovery_offset_m"] = round(offset, 5)
    out = dict(plan)
    out["stages"] = stages
    out["recovered"] = True
    return out


def record(original_evidence, decision, source_run):
    """Build an audit record; keeps the original failure intact."""
    blob = json.dumps(decision).lower()
    for word in PROTECTED_TOPICS:
        if word in blob and decision["action"] != "no_recovery":
            raise ValueError("recovery decision touches a protected topic: " + word)
    return {"record_kind": "RECOVERY_DECISION", "source_run": source_run,
            "original_evidence": original_evidence, "decision": decision,
            "original_failure_preserved": True}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--attempt", type=int, default=1)
    args = ap.parse_args(argv)
    ev = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
    print(json.dumps(decide(ev, args.attempt), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
