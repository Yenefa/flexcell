#!/usr/bin/env python3
"""W5-E2d: explicit action instruction across three models."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent
RUNS = [
    ('rep1', '655de595bad76f5d14e1aa0d8b5cbd85a40461a2aed346f9a621c5208edfe2b4', 3, 3089, 'deepseek-chat'),
    ('rep2', '3bdf3d1d1942c6ea9a862d49c1a4e3906bcdacae5686cc2aca5bed866fa96c11', 2, 1999, 'deepseek-chat'),
    ('rep3', 'c85ffbaed6d3ef86cc663874cbca37a62096e4b5b63772480867737203ed71aa', 2, 1983, 'deepseek-chat'),
    ('rep4', 'bcbb0ff6aab8cbff14fdc16e06f1d3300d480d465154b4be8eb30139dc5923fb', 3, 3069, 'deepseek-chat'),
    ('rep5-v4pro', 'abe77ef974ca8a79e5be39db1129824b172c902f332affb49715b94f0aee3541', 3, 3511, 'deepseek-v4-pro'),
    ('rep6-flash', '86e143d79b4ac982125324657fbb0f39b352f1d5b53df0f3f6491ef77eca6dfb', 3, 3132, 'deepseek-flash'),
]


def main():
    agg = json.loads((HERE / "aggregate.json").read_text())
    for rep, expected, iters, tokens, model in RUNS:
        data = (HERE / rep / "result.json").read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected, rep + " drifted"
        doc = json.loads(data.decode())
        assert doc["success"] is True and doc["false_success"] is False, rep
        assert doc["iterations"] == iters and doc["cost"]["tokens"] == tokens, rep
        verdict = json.loads((HERE / rep / "verdict.json").read_text())
        assert verdict["passed"] is True, rep
        for gate in ("target", "regression_normal", "regression_regrasp"):
            assert verdict[gate]["status"] == "PASS", (rep, gate)
    assert agg["n"] == 6 and agg["success"] == 6
    models = sorted({r["model"] for r in agg["rows"]})
    assert models == ["deepseek-chat", "deepseek-flash", "deepseek-v4-pro"], models
    print(json.dumps({"verdict": "W5E2D_6OF6_THREE_MODELS", "iters": [r[2] for r in RUNS],
                      "tokens": [r[3] for r in RUNS], "models": models}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
