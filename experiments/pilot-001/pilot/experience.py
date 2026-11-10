"""Structured failure reports and machine-readable experience records.

P2 needs three things kept apart (the sprint says only the third counts as
Experience-Driven Improvement):

1. a hand-written repair hint  - what the Level B task text contains;
2. an experience the agent itself derived from execution feedback;
3. an experience the agent actually REUSED on a different task.

This module only builds (1) and (2) from recorded runs. It never invents a
lesson: every field is copied from an archived result/events file, so a report
cannot claim more than the run showed.
"""
import json
from pathlib import Path


def _iterations(events_path):
    calls = []
    for line in Path(events_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") == "iteration":
            calls += [c[0] for c in (row.get("calls") or [])]
    return calls


def failure_report(run_dir):
    """A structured report of one archived run, from its own artifacts."""
    run_dir = Path(run_dir)
    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    calls = _iterations(run_dir / "events.jsonl")
    verdict = result.get("verdict") or {}
    target = verdict.get("target") or {}
    detail = str((result.get("meta") or {}).get("detail") or "")
    return {
        "schema": "flexcell.failure_report/1",
        "run": run_dir.name,
        "model": (result.get("meta") or {}).get("requested_model"),
        "outcome": {
            "success": result.get("success"),
            "target_status": target.get("status"),
            "claim_success": result.get("claim_success"),
            "false_success": result.get("false_success"),
        },
        "cost": {
            "iterations": result.get("iterations"),
            "tokens": (result.get("cost") or {}).get("tokens"),
        },
        "behaviour": {
            "tool_calls": len(calls),
            "by_tool": {name: calls.count(name) for name in sorted(set(calls))},
            "edited_source": calls.count("edit_file") + calls.count("write_file"),
            "ran_scenario": calls.count("run_execution"),
        },
        "detail": detail[:400],
    }


def experience_record(report, defect_class, lesson, evidence):
    """A reusable lesson, but only if it is grounded in a measured run.

    ``lesson`` must be a claim the run actually supports: the caller supplies it,
    and the record keeps the evidence paths so a reader can check it. A record
    whose evidence does not exist is refused rather than stored.
    """
    missing = [str(p) for p in evidence if not Path(p).exists()]
    if missing:
        raise ValueError("evidence missing: %s" % missing)
    if report["outcome"]["success"] is None:
        raise ValueError("report has no outcome; refusing to store a lesson")
    return {
        "schema": "flexcell.experience/1",
        "defect_class": defect_class,
        "observed": {
            "success": report["outcome"]["success"],
            "iterations": report["cost"]["iterations"],
            "tokens": report["cost"]["tokens"],
            "behaviour": report["behaviour"],
        },
        "lesson": lesson,
        "evidence": [str(p) for p in evidence],
        "provenance": "derived from the run above; not hand-written",
    }
