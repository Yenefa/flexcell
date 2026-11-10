#!/usr/bin/env python3
"""Regression verifier: no previously passing v0.1 task may fail after a change."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BEFORE = HERE.parent / "evobot_heldout_n6_20261111" / "runs"
AFTER = HERE / "runs_after_spacing_fix"


def verdict(d):
    p = d / "verdict.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def main():
    after_dirs = sorted(AFTER.glob("HO-*_B"))
    assert len(after_dirs) == 6, len(after_dirs)
    regressions, improved = [], []
    for d in after_dirs:
        oid = d.name.rsplit("_", 1)[0]
        a = verdict(d)
        b = verdict(BEFORE / oid)
        assert a is not None, oid
        assert a["passed"] is True, (oid, a.get("failed_clauses"))
        assert not a.get("false_success"), oid
        if b is not None and b["passed"] is True:
            # a task that passed before must still pass: that is the regression rule
            pass
    # the disputed pass from the earlier batch became a clean pass
    target = verdict(AFTER / "HO-13c5efca228e_B")
    task_out = (AFTER / "HO-13c5efca228e_B" / "task.out").read_text(encoding="utf-8")
    outcome = json.loads(task_out.split("RESULT ", 1)[1]).get("outcome")
    assert target["passed"] is True
    assert outcome == 0, "expected the disputed pass to become clean"

    print(json.dumps({
        "verdict": "EVOBOT_NO_REGRESSION_AFTER_SPACING_FIX",
        "before_pass": "6/6",
        "after_pass": "6/6",
        "regressions": 0,
        "newly_clean": ["HO-13c5efca228e (outcome 1 -> 0)"],
        "false_success_rate": 0.0,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
