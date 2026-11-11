#!/usr/bin/env python3
"""EvoBot Baseline A, first real task execution (T01-train-seed1000).

This is the first time the EvoBot benchmark ran a task on the robot and was graded
by the independent evaluator rather than by the robot itself. It establishes
Baseline A: a deterministic composite executor, handed a stage list derived
mechanically from the spec, with no agent planning involved.

The verifier re-runs the evaluation from the archived observation and the archived
spec, so the verdict is reproduced rather than quoted.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2] / "benchmark" / "evaluators"))
import evaluate as ev


def main():
    spec = json.loads((HERE / "spec.json").read_text(encoding="utf-8"))
    obs = json.loads((HERE / "observation.json").read_text(encoding="utf-8"))
    clean = {k: v for k, v in obs.items() if not k.startswith("_")}
    verdict = ev.evaluate(spec, clean)

    assert verdict["passed"] is True, verdict["failed_clauses"]
    assert verdict["false_success"] is False
    assert verdict["evaluator_version"] == ev.EVALUATOR_VERSION
    # The archived spec records the evaluator version it was GENERATED with. Requiring that to
    # equal today's version would force a rewrite of the archive every time a clause is added,
    # which is exactly how an archive stops being evidence. The version is reported instead, and
    # the clause-level identity is what the regression run established (64/64 archived runs
    # re-grade identically after the 0.2.0 bump).
    assert spec.get("evaluator_version"), "spec must record the version it was made with"

    # both objects were actually measured, not assumed
    assert set(obs["objects"]) == {o["name"] for o in spec["objects"]}
    assert obs["_absent"] == []
    assert set(obs["_provenance"].values()) == {"verify.measured"}

    # the composite really ran both stages
    task = (HERE / "task.out").read_text(encoding="utf-8")
    result = json.loads(task.split("RESULT ", 1)[1])
    assert result["outcome"] == 0 and result["error_code"] == 0
    assert len(result["completed_stage_ids"]) == 2

    # and the measured placement errors are inside the declared tolerance
    dists = {c["clause"]: c["evidence"]["distance_m"] for c in verdict["clauses"]}
    assert all(d < 0.06 for d in dists.values()), dists

    print(json.dumps({
        "verdict": "EVOBOT_T01_BASELINE_A_INDEPENDENTLY_VERIFIED",
        "task_id": spec["task_id"],
        "spec_evaluator_version": spec.get("evaluator_version"),
        "current_evaluator_version": ev.EVALUATOR_VERSION,
        "template_id": spec["template_id"],
        "instruction": spec["instruction"],
        "arm": "A_deterministic_composite",
        "agent_planned": False,
        "stages_completed": result["completed_stage_ids"],
        "placement_errors_m": dists,
        "tolerance_m": 0.06,
        "false_success": verdict["false_success"],
        "false_failure": verdict["false_failure"],
        "capability_level_claimed": "LEVEL_1_EXECUTE (Baseline A only)",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
