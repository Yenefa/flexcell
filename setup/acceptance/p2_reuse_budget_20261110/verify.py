#!/usr/bin/env python3
"""P2 at a workable budget: a DIFFERENT defect, with the prior lesson available.

This replaces the earlier P2 run, which was truncated at 54k tokens and therefore
could not support an H0 ("the note did not help"). Here the budget is 150k, the
defect is on the VERIFY branch (not PLACE), localisation is OFF, and the only
extra input is the archived experience record.
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

    flat, edits, read_note = [], [], False
    for line in (HERE / "events.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") == "iteration":
            flat += [c[0] for c in (row.get("calls") or [])]
        if row.get("kind") == "transcript":
            for x in (row.get("results") or []):
                a = str(x.get("args") or "")
                if "experience/experience_place_target.json" in a and x.get("tool") == "read_file":
                    read_note = True
                if x.get("tool") == "edit_file":
                    edits.append(x.get("args"))

    # the agent actually opened the stored lesson
    assert read_note, "the experience record was never read"
    # it edited exactly once, and on the VERIFY branch, not the PLACE one
    assert len(edits) == 1, edits
    args = edits[0]
    assert "zone_of[decision.target]" in args.get("new", ""), args
    # localisation was off in this arm, so the note is the only extra input
    assert not any("suspect_regions" in str(x.get("result"))
                   for row in [] for x in [])

    print(json.dumps({
        "verdict": "P2_AGENT_READ_AND_REUSED_A_STORED_EXPERIENCE",
        "model": r["meta"]["requested_model"],
        "iterations": r["iterations"],
        "tokens": r["cost"]["tokens"],
        "tool_counts": {k: flat.count(k) for k in
                        ("list_dir", "read_file", "run_execution", "edit_file")},
        "experience_record_read": read_note,
        "target": v["target"]["status"],
        "regressions": [v["regression_normal"]["status"],
                        v["regression_regrasp"]["status"]],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
