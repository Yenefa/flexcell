#!/usr/bin/env python3
"""C3 FSM-vs-MTC comparison: verify the six archived runs (n=3 per arm)."""
import hashlib
import json
from pathlib import Path

RUNS = [
    ('legacy-a', '4e86ae44b2322472e6a150164b99dac89bf4709a0387a5df946b356d1500d7cb', 'fsm', 14.671),
    ('legacy-d', '424b2c245b1c5549b9f0b235190227b0da0f5f086813928b44cfc0a4490b4bbd', 'fsm', 17.853),
    ('legacy-e', '59f8a9f53e80469c42b0f08b28d6d1b77d3e66d0f9ca00e72e55c5fb36cc2620', 'fsm', 14.588),
    ('mtc-b', '6209ce33296138baf696fcd7d8314066347716ca6a8c39f1c9f1507fa8b390e1', 'mtc', 16.771),
    ('mtc-c', '3c804037f70fa23a1dc4fa76da2d75a4f07c99b085d97a27bf8a92a3e239254e', 'mtc', 16.6),
    ('mtc-f', '5c29a0ff849d4fd304e07c4fe3644ef36ef026f8fdf4a5489da74e92d2c44c7b', 'mtc', 24.52),
]


def main():
    rows = []
    for rel, expected, arm, wall in RUNS:
        path = Path(__file__).parent / rel / "result.json"
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected, rel + " drifted"
        doc = json.loads(data.decode())
        task = doc["task"]
        assert doc["status"] == "PASS" and task["outcome"] == "OUTCOME_SUCCEEDED", rel
        assert task["error_code"] == "ERR_NONE", rel
        assert abs(task["wall_seconds"] - wall) < 1e-6, rel
        rows.append({"run": rel, "arm": arm, "wall_seconds": task["wall_seconds"],
                     "evidence_id": task["evidence_id"],
                     "fingerprint": doc["runtime_fingerprint"]})
    agg = json.loads((Path(__file__).parent / "aggregate.json").read_text())
    assert agg["fsm"]["success"] == 3 and agg["mtc"]["success"] == 3
    print(json.dumps({"verdict": "C3_N3_BOTH_ARMS_PASS", "fsm_mean_wall": agg["fsm"]["mean_wall"],
                      "mtc_mean_wall": agg["mtc"]["mean_wall"], "runs": rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
