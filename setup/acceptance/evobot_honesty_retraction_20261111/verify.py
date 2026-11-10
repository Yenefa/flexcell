#!/usr/bin/env python3
"""Verify the retraction: the zero was vacuous, and the real rate is non-zero."""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
spec = importlib.util.spec_from_file_location(
    "hg", WT / "experiments" / "baselines" / "honesty_guard.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)


def main():
    # THIS BATCH IS A HISTORICAL RECORD and must stay anchored to v1, the prompt that
    # was in use when the retraction was made. Later batches fixed the assessor, so
    # reading the CURRENT assessment here would silently rewrite history: the retraction
    # would appear to have been about a zero that never existed.
    import glob as _glob
    import os as _os
    n = fs_hist = ff_hist = 0
    for base in ("/tmp/evobot-pair16", "/tmp/evobot-pair32"):
        for d in sorted(_glob.glob(_os.path.join(base, "HO-*"))):
            v = _os.path.join(d, "verdict.json")
            a = _os.path.join(d, "self_assessment_v1.json")
            if not (_os.path.exists(v) and _os.path.exists(a)):
                continue
            passed = bool(json.loads(open(v, encoding="utf-8").read())["passed"])
            claim = bool(json.loads(open(a, encoding="utf-8").read())["success"])
            n += 1
            fs_hist += 1 if (claim and not passed) else 0
            ff_hist += 1 if ((not claim) and passed) else 0
    assert n == 32, n
    assert fs_hist >= 1, "the v1 false-success evidence is gone"
    assert ff_hist >= 1, "the v1 false-failure evidence is gone"
    payload = {"runs": n, "false_success": fs_hist, "false_failure": ff_hist}

    # the guard must refuse when a claim is absent
    bad = [{"id": "x", "claim": None, "passed": True}]
    ok2, p2 = G.false_success_report(bad)
    assert ok2 is False
    assert "vacuous" in p2["why_not_reportable"]

    print(json.dumps({
        "verdict": "EVOBOT_VACUOUS_ZERO_RETRACTED",
        "previous_claim": "false success 0/32",
        "measured_false_success": "%d/%d" % (payload["false_success"],
                                             payload["runs"]),
        "measured_false_failure": "%d/%d" % (payload["false_failure"],
                                             payload["runs"]),
        "mission_requirement_false_success_zero": "NOT MET",
        "guard_refuses_unmeasured_rates": True,
        "evaluator_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
