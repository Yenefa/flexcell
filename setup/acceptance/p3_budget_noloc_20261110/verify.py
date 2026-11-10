#!/usr/bin/env python3
"""P3: with localisation OFF and 3.75x budget, the agent repairs the defect.

This overturns the earlier attribution. The three 40k runs never edited, but they
were truncated, so "localisation cost is the binding constraint" was never
established - only assumed. With room, traversal DOES converge.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent / "run1"


def main():
    r = json.loads((HERE / "result.json").read_text())
    v = r["verdict"]
    assert v["target"]["status"] == "PASS", v["target"]
    assert v["regression_normal"]["status"] == "PASS"
    assert v["regression_regrasp"]["status"] == "PASS"
    assert v["build"]["returncode"] == 0
    assert r["claim_success"] is False and r["false_success"] is False

    flat, edits, saw = [], [], False
    for line in (HERE / "events.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") == "iteration":
            flat += [c[0] for c in (row.get("calls") or [])]
        if row.get("kind") == "transcript":
            for x in (row.get("results") or []):
                if "suspect_regions" in str(x.get("result")):
                    saw = True
                if x.get("tool") == "edit_file":
                    edits.append(x.get("args"))

    # the localisation really was off, otherwise this proves nothing new
    assert saw is False, "suspect_regions leaked into this arm"
    # it did edit, and the edit is the correct one
    assert len(edits) == 1, edits
    args = edits[0]
    assert "zone_of[self._obj_a]" in args.get("old", ""), args
    assert "zone_of[decision.target]" in args.get("new", ""), args
    # and it paid for it in traversal, which is the point
    assert flat.count("list_dir") > 0

    print(json.dumps({
        "verdict": "P3_BUDGET_NOT_CAPABILITY_LEVEL_C_FAILURES_WERE_TRUNCATION",
        "model": r["meta"]["requested_model"],
        "iterations": r["iterations"],
        "tokens": r["cost"]["tokens"],
        "tool_counts": {k: flat.count(k) for k in
                        ("list_dir", "read_file", "run_execution", "edit_file")},
        "suspect_regions_seen": saw,
        "target": v["target"]["status"],
        "regressions": [v["regression_normal"]["status"],
                        v["regression_regrasp"]["status"]],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
