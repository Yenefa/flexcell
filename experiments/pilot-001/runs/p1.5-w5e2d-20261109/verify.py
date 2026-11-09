#!/usr/bin/env python3
"""W5-E2d: explicit action instruction, two real-Gazebo pilots."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent
RUNS = [
    ('rep1', '655de595bad76f5d14e1aa0d8b5cbd85a40461a2aed346f9a621c5208edfe2b4', 3, 3089, 2),
    ('rep2', '3bdf3d1d1942c6ea9a862d49c1a4e3906bcdacae5686cc2aca5bed866fa96c11', 2, 1999, 2),
]


def main():
    agg = json.loads((HERE / "aggregate.json").read_text())
    for rep, expected, iters, tokens, reads in RUNS:
        data = (HERE / rep / "result.json").read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected, rep + " drifted"
        doc = json.loads(data.decode())
        assert doc["success"] is True and doc["false_success"] is False, rep
        assert doc["iterations"] == iters and doc["cost"]["tokens"] == tokens, rep
        verdict = json.loads((HERE / rep / "verdict.json").read_text())
        assert verdict["passed"] is True, rep
        assert verdict["target"]["status"] == "PASS", rep
        assert verdict["regression_normal"]["status"] == "PASS", rep
        assert verdict["regression_regrasp"]["status"] == "PASS", rep
    assert agg["n"] == 2 and agg["success"] == 2
    print(json.dumps({"verdict": "W5E2D_2OF2", "iters": [r[2] for r in RUNS],
                      "tokens": [r[3] for r in RUNS], "reads_before_write": [r[4] for r in RUNS]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
