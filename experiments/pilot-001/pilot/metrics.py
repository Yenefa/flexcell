"""Aggregate run results into pre-registered metrics."""
import json
from collections import defaultdict
from pathlib import Path


def summarize(runs):
    """runs: list of result dicts from runner.run_one."""
    by_arm = defaultdict(list)
    for r in runs:
        by_arm[r["arm"]].append(r)

    def arm_row(arm):
        rows = by_arm.get(arm, [])
        n = len(rows)
        if not n:
            return {"n": 0}
        return {
            "n": n,
            "task_success": round(sum(1 for r in rows if r["success"]) / n, 4),
            "first_pass": round(sum(1 for r in rows if r.get("first_pass")) / n, 4),
            "mean_iterations": round(sum(r["iterations"] for r in rows) / n, 4),
            "false_success": sum(1 for r in rows if r.get("false_success")),
            "violations": sum(1 for r in rows if r.get("violation")),
            "mean_evidence": round(sum(r["evidence"]["completeness"] for r in rows) / n, 4),
            "tokens": sum(r["cost"]["tokens"] for r in rows),
            "agent_s": round(sum(r["cost"]["agent_s"] for r in rows), 4),
            "execution_s": round(sum(r["cost"]["execution_s"] for r in rows), 4),
        }

    return {
        "arms": {arm: arm_row(arm) for arm in ("A", "C", "B")},
        "deltas": {
            "C-A": _delta(arm_row("C"), arm_row("A"), "task_success"),
            "B-C": _delta(arm_row("B"), arm_row("C"), "task_success"),
            "B-A": _delta(arm_row("B"), arm_row("A"), "task_success"),
        },
    }


def _delta(hi, lo, key):
    if not hi.get("n") or not lo.get("n"):
        return None
    return round(hi.get(key, 0) - lo.get(key, 0), 4)
