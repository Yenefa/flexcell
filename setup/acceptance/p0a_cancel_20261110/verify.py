#!/usr/bin/env python3
"""P0-A integration: cancel a live PICK and check the safety invariants."""
import json
from pathlib import Path

HERE = Path(__file__).parent

def main():
    run = json.loads((HERE / "run.json").read_text())["observed"]
    # 1) the cancelled goal terminates with the typed cancel result
    assert run["outcome"] == 2, "cancel must end OUTCOME_CANCELED"
    assert run["error_code"] == 32, "cancel must carry ERR_CANCELED"
    # 2) no unmanaged background goal: the trace shows the cancel landed on PICK
    assert any("ERR_CANCELED" in t for t in run["fsm_trace"]), run["fsm_trace"]
    # 3) the next task is NOT allowed to run against an unsafe arm state
    second = run["second_task"]
    assert second["outcome"] != 0, "a task must not succeed right after a cancelled grasp"
    # 4) the refusal is typed, not a silent failure
    assert "canonical_error_code=35" in second["detail"], second["detail"]
    print(json.dumps({"verdict": "P0A_CANCEL_CONTRACT_HELD",
                      "cancel_result": [run["outcome"], run["error_code"]],
                      "second_task_refused": second["error_code"],
                      "quarantine_engaged": run["saw_quarantined"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
