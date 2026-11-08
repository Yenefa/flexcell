#!/usr/bin/env python3
"""MTC treatment-arm qualification (2026-11-09): one real Gazebo run."""
import hashlib
import json
from pathlib import Path

RESULT_SHA256 = 'f0797998e036ab1f379f8df7e0f6814312d59de77c91f5131105dda009d65ffe'


def main():
    path = Path(__file__).with_name("result.json")
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == RESULT_SHA256, "result.json drifted"
    doc = json.loads(data.decode())
    assert doc["status"] == "PASS"
    assert doc["skill_backend"] == "mtc" and doc["backend"] == "velocity_servo"
    assert doc["physical_tasks_dispatched"] == 1
    task = doc["task"]
    assert task["outcome"] == "OUTCOME_SUCCEEDED" and task["error_code"] == "ERR_NONE"
    assert task["fsm_trace"][:3] == ["PICK_A(attempt=1):OK", "PLACE_A:OK", "VERIFY_A(attempt=1):OK"]
    assert doc["runtime_fingerprint"] == "33b420d1698242958c69fea3112f71a86cf3b0d65e2109fa7aa6650c1a116f52"
    print(json.dumps({"verdict": "MTC_QUALIFICATION_PASS", "skill_backend": "mtc",
                      "outcome": task["outcome"], "evidence_id": task["evidence_id"],
                      "runtime_fingerprint": doc["runtime_fingerprint"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
