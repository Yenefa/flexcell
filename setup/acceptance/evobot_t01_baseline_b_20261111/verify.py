#!/usr/bin/env python3
"""EvoBot Baseline B, first agent-planned task (T01-train-seed1000).

Baseline A and B ran the SAME instance against the SAME evaluator. The only
difference is who produced the object->bin mapping: in A it was derived mechanically
from the spec, in B the agent inferred it from the instruction plus perception.

What this verifier checks, in order of what it would be easiest to fake:
  1. the agent reply is the agent's, and the plan came from it;
  2. the observation handed to the agent contained no answer;
  3. the run passed the independent evaluator;
  4. A and B agree on the mapping - so B was not lucky in a different way than A.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "benchmark" / "evaluators"))
import evaluate as ev

ARM_A = HERE.parent / "evobot_t01_baseline_a_20261111"


def main():
    spec = json.loads((HERE / "spec.json").read_text(encoding="utf-8"))
    obs = json.loads((HERE / "observation.json").read_text(encoding="utf-8"))
    reply = json.loads((HERE / "agent_reply.json").read_text(encoding="utf-8"))
    agent_input = json.loads((HERE / "observation_input.json").read_text(encoding="utf-8"))
    plan = json.loads((HERE / "plan.json").read_text(encoding="utf-8"))

    # (1) the plan really came from the model reply
    assert reply["problems"] == [], reply["problems"]
    agent_plan = reply["agent_plan"]
    assert agent_plan and agent_plan["moves"]
    planned = [(m["object"], m["zone"]) for m in agent_plan["moves"]]
    from_plan = [(s["object_name"],) for s in plan["stages"]]
    assert [o for o, _ in planned] == [o[0] for o in from_plan]
    assert reply.get("model") or reply.get("requested_model"), "no model provenance"

    # (2) nothing in the agent input encodes the answer
    blob = json.dumps(agent_input).lower()
    for leak in ["expected", "placement", "evaluator", "tolerance", "unmoved"]:
        assert leak not in blob, leak
    assert set(agent_input) == {"instruction", "objects", "zones", "skills"}

    # (3) independent verdict
    clean = {k: v for k, v in obs.items() if not k.startswith("_")}
    verdict = ev.evaluate(spec, clean)
    assert verdict["passed"] is True, verdict["failed_clauses"]
    assert verdict["false_success"] is False

    # (4) A and B reached the same mapping on this instance
    mapping_b = dict(planned)
    mapping_a = None
    if (ARM_A / "spec.json").exists():
        spec_a = json.loads((ARM_A / "spec.json").read_text(encoding="utf-8"))
        mapping_a = dict(spec_a["expected_goal"]["placement"])
    assert mapping_a is not None, "baseline A record missing; comparison impossible"
    assert mapping_b == mapping_a, (mapping_b, mapping_a)

    dists = {c["clause"]: c["evidence"]["distance_m"] for c in verdict["clauses"]}
    print(json.dumps({
        "verdict": "EVOBOT_T01_BASELINE_B_AGENT_PLANNED_AND_VERIFIED",
        "task_id": spec["task_id"],
        "instruction": spec["instruction"],
        "arm": "B_runtime_agent",
        "agent_planned": True,
        "agent_mapping": mapping_b,
        "agent_reasons": [m.get("why", "") for m in agent_plan["moves"]],
        "agent_confidence": agent_plan.get("confidence"),
        "same_mapping_as_baseline_a": True,
        "placement_errors_m": dists,
        "false_success": verdict["false_success"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
