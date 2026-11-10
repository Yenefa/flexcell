#!/usr/bin/env python3
"""Level C achieved: no location hints, the failure evidence carries its own
localisation. Checks every archived repeat, not just the first one."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent


def load(d):
    r = json.loads((d / "result.json").read_text())
    flat = []
    saw = False
    for line in (d / "events.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") == "iteration":
            flat += [c[0] for c in (row.get("calls") or [])]
        if row.get("kind") == "transcript":
            for x in (row.get("results") or []):
                if "suspect_regions" in str(x.get("result")):
                    saw = True
    return r, flat, saw


def check(d):
    r, flat, saw = load(d)
    v = r["verdict"]
    assert v["target"]["status"] == "PASS", (d.name, v["target"])
    assert v["regression_normal"]["status"] == "PASS", (d.name, v["regression_normal"])
    assert v["regression_regrasp"]["status"] == "PASS", (d.name, v["regression_regrasp"])
    assert v["build"]["returncode"] == 0, (d.name, v["build"])
    # the agent never graded itself
    assert r["claim_success"] is False and r["false_success"] is False, d.name
    # it edited exactly once, and the localisation really was delivered
    assert flat.count("edit_file") == 1, (d.name, flat.count("edit_file"))
    assert saw, (d.name, "the agent never received suspect_regions")
    return {
        "run": d.name,
        "iterations": r["iterations"],
        "tokens": r["cost"]["tokens"],
        "edit_file": flat.count("edit_file"),
        "list_dir": flat.count("list_dir"),
        "run_execution": flat.count("run_execution"),
        "target": v["target"]["status"],
        "regressions": [v["regression_normal"]["status"],
                        v["regression_regrasp"]["status"]],
    }


def main():
    runs = sorted(p for p in HERE.glob("run_*") if (p / "result.json").is_file())
    assert runs, "no archived runs"
    rows = [check(d) for d in runs]
    print(json.dumps({
        "verdict": "W5_LEVELC_ACHIEVED_WITH_EVIDENCE_LOCALISATION",
        "archived_runs": len(rows),
        "runs": rows,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
