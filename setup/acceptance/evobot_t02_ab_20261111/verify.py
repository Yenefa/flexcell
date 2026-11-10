#!/usr/bin/env python3
"""T02 exclusion, both arms, same instance and same evaluator.

T02 is the first template where NOT acting is part of the answer: everything must be
cleared into one bin EXCEPT a named block, which must stay put.

The verifier checks the property that makes this template worth having: the protected
object was measured, and it did not move. That measurement only exists because the
observation now takes ground truth - an untouched object never appears in a skill log,
and the first attempt at this task was graded FAIL for exactly that reason.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "benchmark" / "evaluators"))
import evaluate as ev


def _arm(tag):
    verdict = json.loads((HERE / ("arm%s_verdict.json" % tag)).read_text(encoding="utf-8"))
    obs = json.loads((HERE / ("arm%s_observation.json" % tag)).read_text(encoding="utf-8"))
    return verdict, obs


def main():
    spec = json.loads((HERE / "spec.json").read_text(encoding="utf-8"))
    protected = spec["expected_goal"]["unmoved"]
    assert protected, "T02 must protect at least one object"

    results = {}
    for tag in ("a", "b"):
        verdict, obs = _arm(tag)
        clean = {k: v for k, v in obs.items() if not k.startswith("_")}
        recomputed = ev.evaluate(spec, clean)
        assert recomputed["passed"] is True, (tag, recomputed["failed_clauses"])
        assert verdict["passed"] is True, tag
        assert verdict["false_success"] is False, tag
        # the protected object must be present in the observation, via ground truth
        for name in protected:
            assert name in obs["objects"], (tag, "protected object unmeasured", name)
        # and it must have been checked by the unmoved clause
        clause = [c for c in verdict["clauses"] if c["clause"] == "unmoved:" + protected[0]]
        assert clause and clause[0]["ok"], (tag, clause)
        results[tag] = {
            "passed": True,
            "protected_moved_m": clause[0]["evidence"]["distance_m"],
            "ground_truth_used": obs.get("_ground_truth_used"),
            "clauses": len(verdict["clauses"]),
        }

    # arm B planned only the non-protected object; arm A did the same mechanically
    plan_a = json.loads((HERE / "arma_plan.json").read_text(encoding="utf-8"))
    plan_b = json.loads((HERE / "armb_plan.json").read_text(encoding="utf-8"))
    moved_a = [s["object_name"] for s in plan_a["stages"]]
    moved_b = [s["object_name"] for s in plan_b["stages"]]
    assert moved_a == moved_b, (moved_a, moved_b)
    for name in protected:
        assert name not in moved_a, (name, "protected object was planned to move")

    reply = json.loads((HERE / "armb_agent_reply.json").read_text(encoding="utf-8"))
    assert reply["problems"] == []

    print(json.dumps({
        "verdict": "EVOBOT_T02_EXCLUSION_BOTH_ARMS_VERIFIED",
        "task_id": spec["task_id"],
        "instruction": spec["instruction"],
        "protected": protected,
        "arm_a": results["a"],
        "arm_b": results["b"],
        "both_arms_moved_only": moved_a,
        "agent_uncertainty": reply["agent_plan"].get("uncertainty"),
        "false_success_rate": 0.0,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
