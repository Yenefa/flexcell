#!/usr/bin/env python3
"""W5-E2e: missing-registration defect across two models."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent
RUNS = [
    ('rep1', 'cb305b3a3417dea7a66ad02d5d8a4016f45cf3d400332e439b3851ae6376d5c8', 4, 4063, 'deepseek-chat'),
    ('rep2', '0174fafadeff1dbb847c265d3e50b3f048ea49ed0332034a9ae3c2d538a79783', 4, 4060, 'deepseek-chat'),
    ('rep3-flash', 'e7c5cb42d3a471c2bff013fc7936bfc8093964f9ba5d2c586d2a2c165906d24f', 4, 4321, 'deepseek-flash'),
]


def main():
    agg = json.loads((HERE / "aggregate.json").read_text())
    for rep, expected, iters, tokens, model in RUNS:
        data = (HERE / rep / "result.json").read_bytes()
        _sha_ok = any(
            hashlib.sha256(v).hexdigest() == expected
            for v in (data,
                      data.replace(b"\r\n", b"\n"),
                      data.replace(b"\n", b"\r\n")))
        assert _sha_ok, rep + " drifted"
        doc = json.loads(data.decode())
        assert doc["success"] is True and doc["false_success"] is False, rep
        assert doc["iterations"] == iters and doc["cost"]["tokens"] == tokens, rep
        verdict = json.loads((HERE / rep / "verdict.json").read_text())
        assert verdict["passed"] is True, rep
        for gate in ("target", "regression_normal", "regression_regrasp"):
            assert verdict[gate]["status"] == "PASS", (rep, gate)
        assert "target_box_b" in (HERE / rep / "week1.yaml").read_text(), rep
    assert agg["n"] == 3 and agg["success"] == 3
    print(json.dumps({"verdict": "W5E2E_3OF3_TWO_MODELS", "iters": [r[2] for r in RUNS],
                      "tokens": [r[3] for r in RUNS]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
