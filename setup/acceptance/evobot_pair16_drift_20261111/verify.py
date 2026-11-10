#!/usr/bin/env python3
"""Verify the n=16 paired run with native diagnostics + world-drift detection."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
PREV = HERE.parent / "evobot_pair16_20261111" / "runs"


def load(p):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def main():
    dirs = sorted(RUNS.glob("HO-*"))
    assert len(dirs) == 16, len(dirs)
    b_pass = r_pass = gained = lost = fs = 0
    for d in dirs:
        b = load(d / "verdict_after1.json")
        r = load(d / "verdict.json")
        assert r is not None, d.name
        if r.get("false_success") or (b or {}).get("false_success"):
            fs += 1
        if b and b.get("passed"):
            b_pass += 1
        if r.get("passed"):
            r_pass += 1
        if b and b.get("passed") is False and r.get("passed") is True:
            gained += 1
        if b and b.get("passed") is True and r.get("passed") is False:
            lost += 1
    assert fs == 0, fs
    assert (b_pass, r_pass) == (12, 15), (b_pass, r_pass)
    assert (gained, lost) == (3, 0), (gained, lost)

    # every retry that fired must have been decision-backed, never verdict-backed
    retried = [d for d in dirs if (d / "plan_retry.json").exists()]
    assert len(retried) == 4, len(retried)
    for d in retried:
        dec = load(d / "recovery_decision.json")
        assert dec is not None, d.name
        dd = dec.get("decision") or dec
        assert dd.get("action") in ("resume", "respread", "redispatch", "reobserve"), d.name
         # evidence must come from the action result, not the grader
        ev = load(d / "failure_evidence.json")
        assert "error_code" in ev

    # the pre-fix batch must still be on disk with its lower B score
    assert PREV.is_dir(), "the earlier batch was deleted"
    prev_dirs = sorted(PREV.glob("HO-*"))
    assert len(prev_dirs) == 16

    # code guards: diagnostics and drift detection must both be live
    sys.path.insert(0, str(HERE.parents[2] / "runtime" / "recovery"))
    import diagnostics
    assert hasattr(diagnostics, "enrich")
    drv = (HERE.parents[2] / "runtime" / "recovery" / "recovery_driver.py").read_text()
    assert "world_drifted" in drv
    assert "diagnostics.enrich" in drv

    print(json.dumps({
        "verdict": "EVOBOT_PAIRED_N16_WITH_DIAGNOSTICS_VERIFIED",
        "instances": 16,
        "B_first_try_pass": b_pass,
        "R_after_retry_pass": r_pass,
        "paired_gained": gained,
        "paired_lost": lost,
        "recovery_rate": "3/4",
        "false_success_rate": 0.0,
        "prior_batch_retained": True,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
