#!/usr/bin/env python3
"""T05 relay: the first template where the arms actually differ.

On T01/T02/T04 a deterministic rule engine (A-prime, no model) solved the same tasks as
the agent, so those templates had no discriminating power. T05 requires an intermediate
stop, and the rule engine has no concept of one.

What this verifier has to prove, in order of how easy each would be to fake:
  1. A-prime genuinely could not plan this instance;
  2. the agent DID plan a two-stage route;
  3. the route was physically executed, not just declared;
  4. the independent evaluator graded the ROUTE, not only the destination.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "benchmark" / "evaluators"))
import evaluate as ev


def main():
    spec = json.loads((HERE / "spec.json").read_text(encoding="utf-8"))
    obs = json.loads((HERE / "observation.json").read_text(encoding="utf-8"))
    reply = json.loads((HERE / "agent_reply.json").read_text(encoding="utf-8"))
    apr = json.loads((HERE / "a_prime_plan.json").read_text(encoding="utf-8"))
    clean = {k: v for k, v in obs.items() if not k.startswith("_")}

    # (1) the rule engine refused instead of guessing
    assert apr["planned"] is False, "A-prime unexpectedly planned this"
    assert "no rule matches" in apr["refusal"], apr

    # (2) the agent produced a genuine two-stage route on one object
    moves = reply["agent_plan"]["moves"]
    assert reply["problems"] == [], reply["problems"]
    assert len(moves) == 2, moves
    assert moves[0]["object"] == moves[1]["object"], "relay must move ONE object twice"
    assert moves[0]["zone"] != moves[1]["zone"], "relay must stop somewhere else first"

    # (3) the executor recorded both stages
    result = json.loads((HERE / "task.out").read_text(encoding="utf-8").split("RESULT ", 1)[1])
    assert result["outcome"] == 0 and result["error_code"] == 0
    assert len(result["completed_stage_ids"]) == 2, result["completed_stage_ids"]

    # (4) the route was graded, and the intermediate bin was really visited
    visit_clauses = [c for c in ev.evaluate(spec, clean)["clauses"]
                     if c["clause"].startswith("visit:")]
    assert visit_clauses, "no visit clause: the relay route was not graded"
    v = visit_clauses[0]
    assert v["ok"] is True, v
    assert v["evidence"]["observed"] == ["zone_1", "zone_2"], v["evidence"]

    verdict = ev.evaluate(spec, clean)
    assert verdict["passed"] is True, verdict["failed_clauses"]
    assert verdict["false_success"] is False

    print(json.dumps({
        "verdict": "EVOBOT_T05_RELAY_AGENT_ONLY_VERIFIED",
        "task_id": spec["task_id"],
        "instruction": spec["instruction"],
        "arm_a_prime": {"planned": False, "refusal": apr["refusal"]},
        "arm_b": {"planned": True,
                  "route": [[m["object"], m["zone"]] for m in moves],
                  "confidence": reply["agent_plan"].get("confidence")},
        "executed_stages": result["completed_stage_ids"],
        "visit_clause": v["evidence"],
        "discriminates_arms": True,
        "false_success": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
