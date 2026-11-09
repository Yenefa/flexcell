#!/usr/bin/env python3
"""W5-E2b: verified improvement on the real stack, three repetitions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent
RUNS = [
    ('rep1', 'aa3ab527ab2a904eff5f551913947f2b8a6d1ee1953f48adbffa432ee6669472', 5, 5161),
    ('rep2', 'a3df61c77aa2bbb7d02809e166c6321abe4f388bf30262a7f17fbeb5113d7807', 3, 2668),
    ('rep3', 'ca5d388d7490a0634bba338c6bcd53bb67fab88852fb452c8d18d70347657d86', 3, 2668),
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
        assert verdict["target"]["status"] == "PASS" and verdict["regression"]["status"] == "PASS", rep
    assert agg["n"] == 3 and agg["success"] == 3
    print(json.dumps({"verdict": "W5E2B_3OF3", "iters": agg["iters"], "tokens": agg["tokens"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
