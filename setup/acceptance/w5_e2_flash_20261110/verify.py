#!/usr/bin/env python3
"""Independent check of the two Flash reproductions (E2d, E2e)."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent


def check(path, label):
    r = json.loads(path.read_text())
    v = r["verdict"]
    assert r["success"] is True, (label, r["success"])
    assert r["false_success"] is False, (label, "false_success set")
    assert v["target"]["status"] == "PASS", (label, v["target"])
    assert v["regression_normal"]["status"] == "PASS", (label, v["regression_normal"])
    assert v["regression_regrasp"]["status"] == "PASS", (label, v["regression_regrasp"])
    return {
        "experiment": label,
        "model": r["meta"]["requested_model"],
        "iterations": r["iterations"],
        "tokens": r["cost"]["tokens"],
        "gates": [v["target"]["status"], v["regression_normal"]["status"],
                  v["regression_regrasp"]["status"]],
    }


def main():
    rows = [check(HERE / "e2d_result.json", "E2d"),
            check(HERE / "e2e_result.json", "E2e")]
    print(json.dumps({"verdict": "E2_FLASH_REPRODUCED", "runs": rows}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
