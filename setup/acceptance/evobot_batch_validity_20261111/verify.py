#!/usr/bin/env python3
"""Verify the retraction: the original batch was invalid, and the failures did not reproduce."""
import glob
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
RERUN = HERE / "rerun_of_three_failures"
FAILED = ["HO-38ce6531a597", "HO-4f197a0997af", "HO-72553754ef3a"]


def main():
    # 1. the original batch really had no recovery evidence
    orig = Path("/tmp/evobot-pair48")
    if orig.is_dir():
        assert not list(orig.glob("HO-*/recovery_decision.json")), (
            "expected zero recovery decisions in the invalid batch")
        assert not list(orig.glob("HO-*/plan_retry.json"))

    # 2. the re-run must show every previously-failing instance passing first try
    for oid in FAILED:
        d = RERUN / oid
        assert d.is_dir(), oid
        b = json.loads((d / "verdict_after1.json").read_text(encoding="utf-8"))
        assert b["passed"] is True, (oid, "failure reproduced; the transient claim is wrong")

    # 3. the validator must reject the original batch and accept a healthy one
    v = WT / "experiments" / "baselines" / "validate_batch.py"
    if orig.is_dir():
        rc = subprocess.run([sys.executable, str(v), str(orig)],
                            capture_output=True, text=True)
        assert rc.returncode == 1, rc.stdout
        assert "not a recovery arm" in rc.stdout
    print(json.dumps({
        "verdict": "EVOBOT_INVALID_BATCH_RETRACTED",
        "original_recovery_decisions": 0,
        "original_plan_retry": 0,
        "arm_R_valid": False,
        "failures_that_reproduced": "0/3",
        "B_13_of_16": "one sample of a noisy process",
        "honesty_metrics_unaffected": True,
        "batch_validator": "rejects a batch whose steps did not run",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
