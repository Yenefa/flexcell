#!/usr/bin/env python3
"""C12: capability comparison FSM vs MTC on three scenarios."""
import json
from pathlib import Path

HERE = Path(__file__).parent

def main():
    doc = json.loads((HERE / "runs.json").read_text())
    rows = doc["rows"]
    by = {}
    for row in rows:
        by.setdefault((row["scenario"], row["arm"]), []).append(row)
    def outcomes(scen, arm):
        return [r["status"] for r in by[(scen, arm)]]
    assert outcomes("A", "legacy") == ["PASS", "PASS"]
    assert outcomes("A", "mtc") == ["PASS", "PASS"]
    assert outcomes("B", "legacy") == ["ROBOT_FAILURE", "ROBOT_FAILURE"]
    assert outcomes("B", "mtc") == ["ROBOT_FAILURE", "ROBOT_FAILURE"]
    assert all(r["error"] == "ERR_SAFETY_REJECTED" for r in by[("B", "legacy")] + by[("B", "mtc")])
    assert outcomes("C", "legacy") == ["PASS", "PASS"]
    assert outcomes("C", "mtc") == ["PASS", "PASS"]
    print(json.dumps({"verdict": "C12_NO_CAPABILITY_ASYMMETRY",
                      "A": "both PASS", "B": "both refused by the safety gate",
                      "C": "both PASS",
                      "note": "negative result: no MTC-only capability observed"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
