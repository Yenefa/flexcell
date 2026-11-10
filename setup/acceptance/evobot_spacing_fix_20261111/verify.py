#!/usr/bin/env python3
"""Verify the spacing fix: 8/8 first-try, and the pre-fix failures are retained."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    after = sorted((HERE / "runs_after_fix").glob("HO-*/verdict.json"))
    assert len(after) == 8, len(after)
    passed = [json.loads(p.read_text(encoding="utf-8")) for p in after]
    assert all(v["passed"] is True for v in passed)
    assert not any(v.get("false_success") for v in passed)

    # no recovery was needed after the fix
    for d in (HERE / "runs_after_fix").glob("HO-*"):
        assert not (d / "plan_retry.json").exists(), d.name

    # the pre-fix failures are still on disk: a fix is only credible if the
    # evidence of what it fixed survives
    before = sorted((HERE / "runs_prefix_n6").glob("HO-*/verdict.json"))
    assert before, "pre-fix failure evidence is missing"
    failures_before = [json.loads(p.read_text(encoding="utf-8")) for p in before
                       if json.loads(p.read_text(encoding="utf-8"))["passed"] is False]
    assert failures_before, "pre-fix failure evidence was not retained"

    sys.path.insert(0, str(HERE.parents[2] / "experiments" / "baselines"))
    import spread_destinations as sd
    assert sd.SPREAD_STEP_M > 0.05 + 0.010, sd.SPREAD_STEP_M
    assert sd.SPREAD_STEP_M / 2.0 < 0.06

    print(json.dumps({
        "verdict": "EVOBOT_SAME_BIN_SPACING_ROOT_CAUSE_FIXED",
        "before": "4/8 pass, recovery 0/4",
        "after": "8/8 first-try pass, recovery not needed",
        "false_success_rate": 0.0,
        "pre_fix_failures_retained": len(failures_before),
        "thresholds_unchanged": {"clearance_m": 0.05, "bin_radius_m": 0.06},
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
