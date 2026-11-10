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


def execution_evidence(task_out):
    p = Path(task_out)
    if not p.exists() or "RESULT " not in p.read_text(encoding="utf-8"):
        return {"error_code": None, "detail": "no terminal action result",
                "completed_stage_ids": []}
    result = json.loads(p.read_text(encoding="utf-8").split("RESULT ", 1)[1])
    return {"outcome": result.get("outcome"), "error_code": result.get("error_code"),
            "detail": result.get("detail", ""),
            "completed_stage_ids": result.get("completed_stage_ids") or []}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--attempt", type=int, default=1)
    ap.add_argument("--ground-truth")
    args = ap.parse_args(argv)
    run = Path(args.run)
    ev = execution_evidence(run / "task.out")
    (run / "failure_evidence.json").write_text(json.dumps(ev, indent=2) + "\n",
                                               encoding="utf-8")

    if ev.get("outcome") == 0 and ev.get("error_code") == 0:
        (run / "recovery_decision.json").write_text(json.dumps(
            {"action": "no_recovery", "reason": "first attempt succeeded"}, indent=2)
            + "\n", encoding="utf-8")
        print("no recovery needed")
        return 0

    decision = recover.decide(ev, attempt=args.attempt)
    action = decision["action"]

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
            retried = recover.apply_respread(plan)
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
