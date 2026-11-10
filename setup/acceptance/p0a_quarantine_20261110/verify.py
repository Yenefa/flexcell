#!/usr/bin/env python3
"""P0-A: the quarantine path actually engages in a live ROS graph."""
import json
from pathlib import Path

HERE = Path(__file__).parent


def main():
    run = json.loads((HERE / "run.json").read_text())["observed"]
    assert "stop unconfirmed" in run["detail"], run["detail"]
    assert run["saw_quarantined"] is True
    second = run["second_task"]
    assert second["outcome"] != 0
    assert second["error_code"] == 50, second
    assert "quarantine active" in second["detail"]
    assert run["reset"]["success"] is True
    assert "cleared" in run["reset"]["message"]
    print(json.dumps({
        "verdict": "P0A_QUARANTINE_ENGAGED_AND_CLEARED",
        "cancel_result": [run["outcome"], run["error_code"]],
        "task_state_saw_quarantined": run["saw_quarantined"],
        "second_task_error_code": second["error_code"],
        "reset_success": run["reset"]["success"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
