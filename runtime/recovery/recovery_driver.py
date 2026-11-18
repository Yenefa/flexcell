#!/usr/bin/env python3
"""Drive recovery from EXECUTION evidence, never from the graded verdict.

TRIGGER RULE (the important part): recovery is decided from the composite action result
(outcome / error_code / detail / completed_stage_ids), NOT from the evaluator verdict.
Retrying because the evaluator said FAIL would be manufacturing success. The evaluator
is consulted only after all attempts, to grade the final world state.

Two recovery paths, both bounded to one retry:
  respread - nothing committed; widen same-bin spacing. No grading change.
  resume   - some stages committed; rebuild the plan from MEASURED object positions so
             the declared initial_objects match reality. Requires --ground-truth.
"""
import argparse
import json
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WT / "runtime" / "recovery"))
import recover
import diagnostics
import goal_check


def execution_evidence(task_out):
    p = Path(task_out)
    if not p.exists() or "RESULT " not in p.read_text(encoding="utf-8"):
        return {"error_code": None, "detail": "no terminal action result",
                "completed_stage_ids": []}
    result = json.loads(p.read_text(encoding="utf-8").split("RESULT ", 1)[1])
    return {"outcome": result.get("outcome"), "error_code": result.get("error_code"),
            "detail": result.get("detail", ""),
            "completed_stage_ids": result.get("completed_stage_ids") or []}


def _experience_kwargs(args):
    """Resolve reviewed live parameters, WITHOUT importing the experience package at module
    load. Failure is a refusal ({}), never an exception: a broken experience lookup must not
    take down a recovering robot."""
    if not (args.experience_asset and args.experience_entries):
        return {}, "no --experience-asset/--experience-entries: frozen baseline defaults"
    try:
        root = str(WT)
        if root not in sys.path:
            sys.path.insert(0, root)
        from evolution.experience.live_binding import resolve
        return resolve(args.experience_asset, "executor_recovery",
                       args.experience_entries,
                       review_ledger=getattr(args, "experience_review_ledger", None))
    except Exception as exc:  # noqa: BLE001 - fail closed, keep the defaults
        return {}, "experience binding unavailable: %s" % exc


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--attempt", type=int, default=1)
    ap.add_argument("--ground-truth")
    # OPT-IN live experience binding. With no --experience-asset/--experience-entries the
    # call below is byte-identical to the frozen baseline: apply_respread uses its defaults.
    # When both are supplied, live_binding.resolve() re-checks the chain, ACTIVE+latest
    # status, an INDEPENDENT ACCEPT and a numeric callable from the ENTRY (not the asset's
    # cached fields). Any gate failure returns {} and the defaults are used. A refusal can
    # therefore never break a run or drive a robot from an unreviewed artifact.
    ap.add_argument("--experience-asset")
    ap.add_argument("--experience-entries")
    ap.add_argument("--experience-review-ledger",
                    help="an independent review ledger keyed by entry_id; without it no "
                         "entry can authorise a live parameter change")
    args = ap.parse_args(argv)
    run = Path(args.run)
    ev = execution_evidence(run / "task.out")
    # fold in per-stage native results so a generic err 62 becomes attributable
    ev = diagnostics.enrich(ev, run)
    (run / "failure_evidence.json").write_text(json.dumps(ev, indent=2) + "\n",
                                               encoding="utf-8")

    if ev.get("outcome") == 0 and ev.get("error_code") == 0:
        (run / "recovery_decision.json").write_text(json.dumps(
            {"action": "no_recovery", "reason": "first attempt succeeded"}, indent=2)
            + "\n", encoding="utf-8")
        print("no recovery needed")
        return 0

    # ---- is the goal ALREADY met, whatever task.out says? ----------------------
    # The FSM conclusion can be a false negative: measured over 32 validated runs, 2 had
    # the task report failure while the box was already released and inside the target
    # zone, with the skill own verifier agreeing. Blindly retrying wasted a full
    # pick-and-place cycle and, worse, made "arm R" look exercised when it was not.
    # This uses ONLY the plan own declared tolerance and the measured positions, never the
    # held-out answer or the evaluator tolerance, so it cannot manufacture a pass.
    if args.ground_truth:
        try:
            gt_now = json.loads(Path(args.ground_truth).read_text(encoding="utf-8"))
            plan_now = json.loads((run / "plan.json").read_text(encoding="utf-8"))
            satisfied, goal_detail = goal_check.check(plan_now,
                                                      gt_now.get("objects") or {})
            (run / "goal_check.json").write_text(
                json.dumps(goal_detail, indent=2) + "\n", encoding="utf-8")
            if satisfied:
                (run / "recovery_decision.json").write_text(json.dumps({
                    "action": "no_recovery",
                    "reason": "goal already satisfied by measurement",
                    "task_out_said": {"outcome": ev.get("outcome"),
                                      "detail": ev.get("detail")},
                    "goal_check": goal_detail,
                }, indent=2) + "\n", encoding="utf-8")
                print("no recovery: goal already satisfied by measurement")
                return 0
        except (ValueError, OSError, KeyError) as exc:
            (run / "goal_check_error.txt").write_text(str(exc), encoding="utf-8")

    decision = recover.decide(ev, attempt=args.attempt)
    action = decision["action"]

    # A stage that FAILED can still have moved the world: pick succeeds, place fails,
    # the box ends up somewhere else, and completed_stage_ids stays EMPTY. Keying
    # "world changed" on committed stages alone therefore misses exactly the case that
    # matters - two runs replayed their original plan and were rejected with
    # "state drift or occupied destination" because initial_objects no longer held.
    # So when measured positions disagree with the declared ones, prefer a resume plan
    # rebuilt from the measurement.
    world_drifted = False
    if args.ground_truth:
        try:
            gt = json.loads(Path(args.ground_truth).read_text(encoding="utf-8"))
            plan_now = json.loads((run / "plan.json").read_text(encoding="utf-8"))
            measured = gt.get("objects") or {}
            for obj in plan_now.get("initial_objects", []):
                name = obj["object_name"]
                if name not in measured:
                    continue
                dx = float(measured[name][0]) - float(obj["position"][0])
                dy = float(measured[name][1]) - float(obj["position"][1])
                if (dx * dx + dy * dy) ** 0.5 > 0.02:
                    world_drifted = True
                    break
        except (ValueError, OSError, KeyError):
            world_drifted = False
    if world_drifted and action in ("redispatch", "reobserve", "respread"):
        decision = dict(decision, action="resume_required",
                        why="measured state no longer matches the declared plan")
        action = "resume_required"

    if action == "resume_required" and args.ground_truth:
        try:
            gt = json.loads(Path(args.ground_truth).read_text(encoding="utf-8"))
            plan = json.loads((run / "plan.json").read_text(encoding="utf-8"))
            resumed = recover.build_resume_plan(
                plan, decision.get("committed_stages"), gt.get("objects") or {})
        except (ValueError, OSError) as exc:
            (run / "recovery_blocked.txt").write_text(str(exc), encoding="utf-8")
            print("resume refused:", exc)
            (run / "recovery_decision.json").write_text(
                json.dumps({"decision": decision, "resume_refused": str(exc)}, indent=2)
                + "\n", encoding="utf-8")
            return 1
        (run / "plan_retry.json").write_text(json.dumps(resumed, indent=2) + "\n",
                                             encoding="utf-8")
        decision = dict(decision, action="resume")

    (run / "recovery_decision.json").write_text(
        json.dumps(recover.record(ev, decision, str(run)), indent=2) + "\n",
        encoding="utf-8")

    if decision["action"] == "respread":
        plan = json.loads((run / "plan.json").read_text(encoding="utf-8"))
        try:
            # The avoid list is the OTHER objects' declared positions. Passing it lets the
            # respread choose its axis instead of always walking +x, which is how the T13
            # retry put a landing point 46 mm from box_b and was refused as occupied.
            avoid = [o["position"][:2] for o in plan.get("initial_objects", [])
                     if o.get("position")]
            # The reviewed experience parameters, if any. resolve() is fail-closed and
            # OPT-IN: with no flags it returns {} and the call keeps its original defaults.
            kwargs, binding_why = _experience_kwargs(args)
            (run / "experience_binding.json").write_text(json.dumps(
                {"consumer": "executor_recovery", "kwargs": kwargs,
                 "why": binding_why}, indent=2) + "\n", encoding="utf-8")
            retried = recover.apply_respread(plan, avoid=avoid, **kwargs)
        except ValueError as exc:
            (run / "recovery_blocked.txt").write_text(str(exc), encoding="utf-8")
            print("respread refused:", exc)
            return 1
        (run / "plan_retry.json").write_text(json.dumps(retried, indent=2) + "\n",
                                             encoding="utf-8")
    elif decision["action"] == "resume":
        pass
    elif decision["action"] in ("redispatch", "reobserve"):
        (run / "plan_retry.json").write_text(
            (run / "plan.json").read_text(encoding="utf-8"), encoding="utf-8")
    else:
        print("no recovery action:", decision["action"])
        return 1

    print(json.dumps({"action": decision["action"],
                      "failure_class": decision["failure_class"],
                      "measured_reason": decision.get("measured_reason")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
