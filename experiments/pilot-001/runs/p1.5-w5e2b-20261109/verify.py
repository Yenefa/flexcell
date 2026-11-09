#!/usr/bin/env python3
"""W5-E2b: verified improvement on the real stack (n=1)."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent

def main():
    res = json.loads((HERE / "result.json").read_text())
    verdict = json.loads((HERE / "verdict.json").read_text())
    agg = json.loads((HERE / "aggregate.json").read_text())
    assert hashlib.sha256((HERE / "result.json").read_bytes()).hexdigest() == agg["sha_result"]
    assert hashlib.sha256((HERE / "verdict.json").read_bytes()).hexdigest() == agg["sha_verdict"]
    assert res["success"] is True and res["false_success"] is False
    assert verdict["passed"] is True
    assert verdict["target"]["status"] == "PASS" and verdict["regression"]["status"] == "PASS"
    cfg = (HERE / "week1.yaml").read_text()
    assert "zone_2_x: 0.25" in cfg
    print(json.dumps({"verdict": "W5E2B_VERIFIED_IMPROVEMENT", "iters": res["iterations"],
                      "target": verdict["target"]["status"], "regression": verdict["regression"]["status"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
