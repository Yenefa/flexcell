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
sys.path.insert(0, str(WT))
from runtime.recovery import failure_classification as diagnosis
from runtime.planner import spread_destinations as sd

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
    """Return a recovery decision dict. Pure function of the measured evidence.

    PARTIAL-COMMIT RULE, learned by running it on the robot: if the first attempt
    committed any stage, the world has already changed. Replaying the whole plan is
    then invalid by construction - the plan declares initial_objects that no longer
    hold, so the composite rejects it with "state drift or occupied destination"
    before stage 0 even starts. Two real runs failed exactly that way after a
    respread. So replay is refused and the honest label is resume_required, which is
    NOT the same as "recovery failed".
    """
    cls, reason = diagnosis.classify(evidence)
    committed = evidence.get("completed_stage_ids") or []
    if committed:
        return {"action": "resume_required", "failure_class": cls,
                "measured_reason": reason, "attempt": attempt, "budget": MAX_RETRIES,
                "committed_stages": list(committed),
                "why": "stages already committed; replay would contradict the "
                       "measured world state. A resumable plan is needed and is "
                       "not implemented."}
    if attempt > MAX_RETRIES:
        return {"action": "no_recovery", "failure_class": cls,
                "reason": "retry budget exhausted", "measured_reason": reason}
    action = ACTION_TABLE.get(cls, "no_recovery")
    return {"action": action, "failure_class": cls, "measured_reason": reason,
            "attempt": attempt, "budget": MAX_RETRIES}


def apply_respread(plan, spread_step=0.090, bin_radius=0.06, cluster_m=0.12,
                   avoid=None, clearance=0.05):
    """Widen spacing for stages that land in the SAME bin.

    TWO BUGS FIXED HERE, both found by running it on the robot:

    1. The first version grouped stages by EXACT equal place_pose. But the normal
       plan builder already offsets same-bin stages by 56 mm, so they were never
       "equal" and respread changed NOTHING - plan_retry.json came out byte-identical
       to plan.json and the retry failed the same way.
    2. 56 mm of separation is only 6 mm above the 50 mm clearance, and measured
       drift is around 10 mm, so the effective gap fell below clearance and the
       composite rejected stage 2 with "occupied destination".

    So stages are now grouped by DISTANCE (anything within cluster_m of an existing
    group centre joins it) and the default spacing is 90 mm: clearance 50 mm plus a
    drift allowance. This WIDENS separation, it never relaxes a threshold, and it
    refuses if the result would leave the declared bin radius.
    """
    import math
    stages = [dict(s, place_pose=list(s["place_pose"])) for s in plan["stages"]]
    groups = []          # list of {"centre": [x,y], "idx": [..]}
    for i, s in enumerate(stages):
        x, y = float(s["place_pose"][0]), float(s["place_pose"][1])
        for g in groups:
            if math.hypot(x - g["centre"][0], y - g["centre"][1]) <= cluster_m:
                g["idx"].append(i)
                break
        else:
            groups.append({"centre": [x, y], "idx": [i]})
    own = [[float(a[0]), float(a[1])] for a in (avoid or [])]

    def _margin(points):
        if not own:
            return float("inf")
        return min(math.hypot(px - ax, py - ay)
                   for px, py in points for ax, ay in own)

    for g in groups:
        idxs = g["idx"]
        if len(idxs) < 2:
            continue
        # INERT WHEN THE GROUP ALREADY MEETS THE CONTRACT (2026-11-18). Before this the
        # function widened EVERY cluster within cluster_m, including clusters that were
        # already spread. On the archive that touched 127 plans and 94 of them needed no
        # change at all - and because the axis is chosen by margin, those 94 were not
        # merely rewritten, they were ROTATED: T03-train-seed1000 sits at exactly the
        # 90 mm contract along x, and respread moved both landings to y, displacing them
        # 64 mm for no benefit. A recovery action that moves landings the planner chose
        # deliberately is not a recovery.
        current = min(math.hypot(float(stages[a]["place_pose"][0])
                                - float(stages[b]["place_pose"][0]),
                                float(stages[a]["place_pose"][1])
                                - float(stages[b]["place_pose"][1]))
                      for i, a in enumerate(idxs) for b in idxs[i + 1:])
        if current >= spread_step - 1e-9:
            continue
        cx = sum(float(stages[i]["place_pose"][0]) for i in idxs) / len(idxs)
        cy = sum(float(stages[i]["place_pose"][1]) for i in idxs) / len(idxs)
        offsets = [(rank - (len(idxs) - 1) / 2.0) * spread_step
                   for rank in range(len(idxs))]
        # AXIS IS CHOSEN, NOT ASSUMED (2026-11-18). Before this, the offsets always ran
        # along +x. On the archived T13 plan that pushed the second landing point to
        # 46 mm from box_b's spawn - below the 50 mm clearance contract - so the retry
        # was refused as "occupied destination" for the third time, this time by the
        # recovery path rather than the planner. The planner-side spread had already
        # solved it by choosing between axes; the executor-side respread had not, and one
        # delivery address fixing it did not fix the other. With no avoid list supplied
        # the behaviour is byte-identical to before (x axis), so every existing caller and
        # test is unaffected.
        axis = 0
        if own:
            def _pts(ax):
                return [[cx + o, cy] if ax == 0 else [cx, cy + o] for o in offsets]
            margins = {ax: _margin(_pts(ax)) for ax in (0, 1)}
            axis = 1 if margins[1] > margins[0] else 0
            if margins[axis] < clearance:
                raise ValueError(
                    "no respread axis keeps every destination %.3f m clear of the "
                    "other objects; refusing rather than emitting a plan that will be "
                    "rejected on the robot" % clearance)
        for rank, i in enumerate(idxs):
            offset = offsets[rank]
            cand = ([cx + offset, cy] if axis == 0 else [cx, cy + offset])
            if abs(offset) > bin_radius:
                raise ValueError("respread would leave the %.3f m bin" % bin_radius)
            stages[i]["place_pose"] = cand + [float(stages[i]["place_pose"][2])]
            stages[i]["recovery_offset_m"] = round(offset, 5)
            stages[i]["recovery_axis"] = "x" if axis == 0 else "y"
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


def build_resume_plan(plan, committed_stage_ids, measured_objects):
    """Rebuild a plan from the CURRENT measured world, keeping only unfinished stages.

    This is what the partial-commit rule needs. Replaying the original plan is invalid
    because its initial_objects no longer hold; resuming from the measured state is the
    real recovery. It changes only bookkeeping that must match reality (initial object
    positions and the stage list). It never touches clearance, tolerance, declared
    destinations, or any grading rule.

    Raises ValueError when nothing is left to do, or when the measured state cannot
    cover the declared objects - a recovery must not invent positions.
    """
    if not isinstance(measured_objects, dict) or not measured_objects:
        raise ValueError("no measured object positions supplied")
    committed = list(committed_stage_ids or [])
    remaining = [s for s in plan["stages"] if s.get("stage_id") not in committed]
    if not remaining:
        raise ValueError("nothing to resume: every stage already committed")
    initial = []
    for obj in plan.get("initial_objects", []):
        name = obj["object_name"]
        if name not in measured_objects:
            raise ValueError("measured state missing object " + name)
        pos = measured_objects[name]
        initial.append({"object_name": name, "position": list(pos[:3])})
    out = dict(plan)
    out["initial_objects"] = initial
    out["stages"] = [dict(s) for s in remaining]
    out["resumed_from_stage_ids"] = committed
    out["recovered"] = True
    out["recovery_kind"] = "resume_from_measured_state"
    return out
