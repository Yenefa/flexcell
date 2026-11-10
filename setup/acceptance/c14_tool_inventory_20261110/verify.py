#!/usr/bin/env python3
"""C14: does a visible tool inventory change tool choice? H0 held."""
import json
from pathlib import Path

HERE = Path(__file__).parent


def main():
    r = json.loads((HERE / "result.json").read_text())
    v = r["verdict"]
    assert v["target"]["status"] != "HARNESS_ERROR", v["target"]
    assert r["success"] is False, "H0 expected: the defect was NOT repaired"
    assert v["target"]["status"] == "ROBOT_FAILURE"
    assert r["claim_success"] is False and r["false_success"] is False

    flat = []
    for line in (HERE / "events.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") == "iteration":
            flat += [c[0] for c in (row.get("calls") or [])]
    counts = {name: flat.count(name) for name in
              ("search_code", "list_dir", "read_file", "run_execution", "edit_file")}

    # the prediction that failed: a visible inventory did NOT induce search
    assert counts["search_code"] == 0, counts
    # the scenario WAS observed, repeatedly
    assert counts["run_execution"] >= 1
    # and no source edit happened
    assert counts["edit_file"] == 0

    print(json.dumps({
        "verdict": "C14_H0_TOOL_CHOICE_NOT_FIXED_BY_INVENTORY",
        "model": r["meta"]["requested_model"],
        "iterations": r["iterations"],
        "tokens": r["cost"]["tokens"],
        "tool_counts": counts,
        "target": v["target"]["status"],
        "regression_normal": v["regression_normal"]["status"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
