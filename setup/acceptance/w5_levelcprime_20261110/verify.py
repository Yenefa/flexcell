#!/usr/bin/env python3
"""Level C-prime: no location hints, but the scenario is run first. Valid judge."""
import json
from pathlib import Path

HERE = Path(__file__).parent


def main():
    r = json.loads((HERE / "result.json").read_text())
    v = r["verdict"]
    # the judge produced a REAL verdict this time (not HARNESS_ERROR)
    assert v["target"]["status"] != "HARNESS_ERROR", v["target"]
    assert v["regression_normal"]["status"] == "PASS", v["regression_normal"]
    # and the honest outcome: the defect was NOT repaired
    assert r["success"] is False
    assert v["target"]["status"] == "ROBOT_FAILURE"
    assert r["claim_success"] is False and r["false_success"] is False

    events = [json.loads(l) for l in (HERE / "events.jsonl").read_text().splitlines() if l.strip()]
    flat = []
    for row in events:
        if row.get("kind") == "iteration":
            flat += [c[0] for c in (row.get("calls") or [])]
    runs = flat.count("run_execution")
    edits = flat.count("edit_file") + flat.count("write_file")
    # it DID see real failure evidence, repeatedly
    assert runs >= 1, "the scenario was never run"
    saw = any(row.get("kind") == "transcript" and
              any(x.get("tool") == "run_execution" and "ROBOT_FAILURE" in str(x.get("result"))
                  for x in (row.get("results") or [])) for row in events)
    assert saw, "no ROBOT_FAILURE evidence reached the agent"
    # and it never edited: the negative result
    assert edits == 0, "the agent did edit; this is no longer a negative result"

    print(json.dumps({
        "verdict": "LEVEL_C_PRIME_VALID_NEGATIVE",
        "model": r["meta"]["requested_model"],
        "iterations": r["iterations"],
        "tokens": r["cost"]["tokens"],
        "executions_run": runs,
        "source_edits": edits,
        "saw_real_failure_evidence": saw,
        "target": v["target"]["status"],
        "regression_normal": v["regression_normal"]["status"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
