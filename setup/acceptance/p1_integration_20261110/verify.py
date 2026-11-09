#!/usr/bin/env python3
"""P1 integration: the real Gazebo stack after P1-A..P1-D."""
import json
from pathlib import Path

HERE = Path(__file__).parent

def main():
    rows = json.loads((HERE / "runs.json").read_text())["rows"]
    assert [r["case"] for r in rows] == ["normal", "dual_object", "regrasp"]
    for row in rows:
        assert row["status"] == "PASS", row
        assert row["error"] == "ERR_NONE", row
    assert len(rows[1]["trace"]) == 6, "the two-object leg must run both legs"
    print(json.dumps({"verdict": "P1_INTEGRATION_3OF3",
                      "walls": [r["wall"] for r in rows]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
