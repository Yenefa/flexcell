#!/usr/bin/env python3
"""MTC treatment-arm qualification (2026-11-09): three real Gazebo runs."""
import hashlib
import json
from pathlib import Path

RUNS = [
    ('result.json', 'f0797998e036ab1f379f8df7e0f6814312d59de77c91f5131105dda009d65ffe'),
    ('r2/result.json', '30b4c502eb89967477b2818c9efbea730d77c7f52d7ab9a7e0478880ff322970'),
    ('r3/result.json', '69409160fa82929963f60d575ebe1a31fab868405deb2e551c459037b5c3098c'),
]
EXPECTED_FP = "33b420d1698242958c69fea3112f71a86cf3b0d65e2109fa7aa6650c1a116f52"


def main():
    rows = []
    for rel, expected in RUNS:
        path = Path(__file__).parent / rel
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected, rel + " drifted"
        doc = json.loads(data.decode())
        assert doc["status"] == "PASS", rel
        assert doc["skill_backend"] == "mtc" and doc["backend"] == "velocity_servo", rel
        assert doc["physical_tasks_dispatched"] == 1, rel
        task = doc["task"]
        assert task["outcome"] == "OUTCOME_SUCCEEDED" and task["error_code"] == "ERR_NONE", rel
        assert doc["runtime_fingerprint"] == EXPECTED_FP, rel
        rows.append({"run": rel, "outcome": task["outcome"], "evidence_id": task["evidence_id"],
                     "runtime_fingerprint": doc["runtime_fingerprint"]})
    assert len(rows) == 3
    print(json.dumps({"verdict": "MTC_QUALIFICATION_N3_PASS", "runs": rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
