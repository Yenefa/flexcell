#!/usr/bin/env python3
"""W5-E2e: second defect type (missing object registration), two runs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent
RUNS = [
    ('rep1', 'cb305b3a3417dea7a66ad02d5d8a4016f45cf3d400332e439b3851ae6376d5c8', 4, 4063),
    ('rep2', '0174fafadeff1dbb847c265d3e50b3f048ea49ed0332034a9ae3c2d538a79783', 4, 4060),
]


def main():
    agg = json.loads((HERE / "aggregate.json").read_text())
    for rep, expected, iters, tokens in RUNS:
        data = (HERE / rep / "result.json").read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected, rep + " drifted"
        doc = json.loads(data.decode())
        assert doc["success"] is True and doc["false_success"] is False, rep
        assert doc["iterations"] == iters and doc["cost"]["tokens"] == tokens, rep
        verdict = json.loads((HERE / rep / "verdict.json").read_text())
        assert verdict["passed"] is True, rep
        for gate in ("target", "regression_normal", "regression_regrasp"):
            assert verdict[gate]["status"] == "PASS", (rep, gate)
        assert "target_box_b" in (HERE / rep / "week1.yaml").read_text(), rep
    assert agg["n"] == 2 and agg["success"] == 2
    print(json.dumps({"verdict": "W5E2E_2OF2", "iters": [r[2] for r in RUNS],
                      "tokens": [r[3] for r in RUNS]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
