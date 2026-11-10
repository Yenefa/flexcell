#!/usr/bin/env python3
"""Level C achieved: no location hints, evidence carries its own localisation."""
import json
from pathlib import Path

HERE = Path(__file__).parent / "run_b_regions_visible"


def counts(d):
    flat = []
    for line in (d / "events.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") == "iteration":
            flat += [c[0] for c in (row.get("calls") or [])]
    return flat


def main():
    r = json.loads((HERE / "result.json").read_text())
    v = r["verdict"]
    # judged by the frozen acceptor, on the real stack
    assert v["target"]["status"] == "PASS", v["target"]
    assert v["regression_normal"]["status"] == "PASS", v["regression_normal"]
    assert v["regression_regrasp"]["status"] == "PASS", v["regression_regrasp"]
    assert v["build"]["returncode"] == 0
    # the agent did not grade itself
    assert r["claim_success"] is False and r["false_success"] is False

    flat = counts(HERE)
    edits = flat.count("edit_file")
    assert edits == 1, edits
    # the localisation was actually delivered (unlike run A, where it was cut)
    saw = False
    for line in (HERE / "events.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") == "transcript":
            for x in (row.get("results") or []):
                if "suspect_regions" in str(x.get("result")):
                    saw = True
    assert saw, "the agent never received suspect_regions"

    print(json.dumps({
        "verdict": "W5_LEVELC_ACHIEVED_WITH_EVIDENCE_LOCALISATION",
        "model": r["meta"]["requested_model"],
        "iterations": r["iterations"],
        "tokens": r["cost"]["tokens"],
        "tool_counts": {k: flat.count(k) for k in
                        ("search_code", "list_dir", "read_file",
                         "run_execution", "edit_file")},
        "target": v["target"]["status"],
        "regressions": [v["regression_normal"]["status"],
                        v["regression_regrasp"]["status"]],
        "claim_success": r["claim_success"],
        "false_success": r["false_success"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
