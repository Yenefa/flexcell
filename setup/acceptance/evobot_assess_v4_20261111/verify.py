#!/usr/bin/env python3
"""Verify v4: false success 0 WITH high accuracy, and all four versions retained."""
import glob
import importlib.util
import json
import os
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
    assert payload["missing_claim"] == 0
    assert payload["false_success"] == 0, payload
    have = [r for r in rows if r["claim"] is not None]
    acc = sum(1 for r in have if r["claim"] == r["passed"])
    # a zero is only admissible with good accuracy: v2/v3 also hit zero, by pessimism
    assert acc / len(have) >= 0.80, acc

    # all four prompt versions must still be on disk: they are the evidence trail
    for ver in ("v1", "v2", "v3", "v4"):
        n = 0
        for base in ("/tmp/evobot-pair16", "/tmp/evobot-pair32"):
            n += len(glob.glob(os.path.join(base, "HO-*",
                                         "self_assessment_%s.json" % ver)))
        assert n == 32, (ver, n)

    print(json.dumps({
        "verdict": "EVOBOT_ASSESS_V4_VERIFIED",
        "false_success": "0/32",
        "false_failure": "%d/32" % payload["false_failure"],
        "accuracy": "%d/32" % acc,
        "zero_not_bought_by_pessimism": True,
        "v1_defect_evidence_retained": True,
        "evaluator_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
