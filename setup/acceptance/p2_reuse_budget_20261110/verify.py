#!/usr/bin/env python3
"""P2 with a control arm: does a stored experience actually reduce repair cost?

Both arms use the SAME VERIFY-branch defect, the SAME 150k budget, no
localisation, and identical task text. The only difference is whether the archived
experience record is present. Without arm B the first result could not be
attributed - the P3 probe already showed the same defect class is solvable without
any note given enough budget.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
ARMS = {"experience": HERE / "run1", "control": HERE / "run_control"}


def load(d):
    r = json.loads((d / "result.json").read_text())
    flat, edits, read_note = [], [], False
    for line in (d / "events.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") == "iteration":
            flat += [c[0] for c in (row.get("calls") or [])]
        if row.get("kind") == "transcript":
            for x in (row.get("results") or []):
                a = str(x.get("args") or "")
                if "experience/experience_place_target.json" in a:
                    read_note = True
                if x.get("tool") == "edit_file":
                    edits.append(x.get("args"))
    v = r["verdict"]
    return {
        "success": r["success"],
        "iterations": r["iterations"],
        "tokens": r["cost"]["tokens"],
        "target": v["target"]["status"],
        "regressions": [v["regression_normal"]["status"],
                        v["regression_regrasp"]["status"]],
        "edit_file": flat.count("edit_file"),
        "list_dir": flat.count("list_dir"),
        "run_execution": flat.count("run_execution"),
        "read_note": read_note,
        "claim_success": r["claim_success"],
        "false_success": r["false_success"],
    }


def main():
    a, b = load(ARMS["experience"]), load(ARMS["control"])
    for arm in (a, b):
        assert arm["target"] == "PASS", arm
        assert arm["regressions"] == ["PASS", "PASS"], arm
        assert arm["claim_success"] is False and arm["false_success"] is False
        assert arm["edit_file"] == 1, arm
    # the arms really differed only in whether the note was read
    assert a["read_note"] is True, "experience arm never read the record"
    assert b["read_note"] is False, "control arm read a record; not a control"
    # both solved it; the experience arm was cheaper on both axes
    cheaper = a["iterations"] <= b["iterations"] and a["tokens"] < b["tokens"]
    print(json.dumps({
        "verdict": "P2_EXPERIENCE_REUSED_AND_CHEAPER" if cheaper else
                   "P2_EXPERIENCE_REUSED_NO_MEASURED_BENEFIT",
        "experience_arm": {k: a[k] for k in
                           ("iterations", "tokens", "list_dir", "run_execution", "read_note")},
        "control_arm": {k: b[k] for k in
                        ("iterations", "tokens", "list_dir", "run_execution", "read_note")},
        "iteration_saving_pct": round(100.0 * (b["iterations"] - a["iterations"])
                                      / b["iterations"], 1),
        "token_saving_pct": round(100.0 * (b["tokens"] - a["tokens"]) / b["tokens"], 1),
        "n_per_arm": 1,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
