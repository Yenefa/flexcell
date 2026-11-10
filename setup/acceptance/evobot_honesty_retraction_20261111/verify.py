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
    rows = G.collect()
    assert len(rows) == 32, len(rows)
    ok, payload = G.false_success_report(rows)
    assert ok is True, payload
    assert payload["missing_claim"] == 0, payload
    # the whole point: the measured rate is NOT zero
    assert payload["false_success"] >= 1, payload
    assert payload["false_failure"] >= 1, payload

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
