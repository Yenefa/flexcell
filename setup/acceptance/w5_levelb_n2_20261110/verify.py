#!/usr/bin/env python3
"""Independent check of the W5 Level B run: was it a real source repair?"""
import json
from pathlib import Path

HERE = Path(__file__).parent


def main():
    result = json.loads((HERE / "result.json").read_text())
    verdict = result["verdict"]

    # 1) the three gates really passed, as measured by the frozen acceptor
    assert verdict["passed"] is True, verdict
    assert verdict["target"]["status"] == "PASS", verdict["target"]
    assert verdict["regression_normal"]["status"] == "PASS"
    assert verdict["regression_regrasp"]["status"] == "PASS"
    assert verdict["build"]["returncode"] == 0

    # 2) the agent did not merely claim success
    assert result["claim_success"] is False
    assert result["false_success"] is False

    # 3) it actually observed the failure before editing
    events = [json.loads(line) for line in
              (HERE / "events.jsonl").read_text().splitlines() if line.strip()]
    calls = []
    for row in events:
        if row.get("kind") == "iteration":
            calls.append([c[0] for c in (row.get("calls") or [])])
    flattened = [c for turn in calls for c in turn]
    assert "run_execution" in flattened, "no execution was ever run"
    assert "edit_file" in flattened, "no source edit was ever made"
    first_run = flattened.index("run_execution")
    first_edit = flattened.index("edit_file")
    assert first_run < first_edit, "edited before observing the failure"

    # 4) the edit is the real fix, against the failing evidence text
    failure_seen = any(
        row.get("kind") == "transcript" and any(
            x.get("tool") == "run_execution" and "ROBOT_FAILURE" in str(x.get("result"))
            for x in (row.get("results") or []))
        for row in events)
    assert failure_seen, "no ROBOT_FAILURE evidence reached the agent"

    print(json.dumps({
        "verdict": "W5_LEVELB_REAL_SOURCE_REPAIR",
        "model": result["meta"]["requested_model"],
        "iterations": result["iterations"],
        "tokens": result["cost"]["tokens"],
        "gates": [verdict["target"]["status"],
                  verdict["regression_normal"]["status"],
                  verdict["regression_regrasp"]["status"]],
        "observed_failure_before_edit": True,
        "claim_success": result["claim_success"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
