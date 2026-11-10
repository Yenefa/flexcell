#!/usr/bin/env python3
"""Verify the first structurally valid batch: recovery demonstrably fired, zero false success."""
import glob
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
RUNS = HERE / "runs"


def read(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return None


def main():
    runs = sorted(RUNS.glob("HO-*"))
    assert len(runs) == 16, len(runs)

    # the structural validator must accept this batch
    rc = subprocess.run([sys.executable,
                         str(WT / "experiments" / "baselines" / "validate_batch.py"),
                         str(RUNS)], capture_output=True, text=True)
    assert rc.returncode == 0, rc.stdout

    b_failed = retried = measured = 0
    fs = ff = passed = 0
    gained = []
    for d in runs:
        b = read(d / "verdict_after1.json") or {}
        r = read(d / "verdict.json") or {}
        obs_p = d / "observation_claimed.json"
        if not obs_p.exists():
            obs_p = d / "observation.json"
        obs = read(obs_p) or {}
        assert obs.get("agent_claim_source") == "measured", d.name
        measured += 1
        passed += 1 if r.get("passed") else 0
        if r.get("false_success"):
            fs += 1
        if r.get("false_failure"):
            ff += 1
        if not b.get("passed"):
            b_failed += 1
            assert (d / "recovery_decision.json").exists(), d.name
        if (d / "plan_retry.json").exists():
            retried += 1
            if not b.get("passed") and r.get("passed"):
                gained.append(d.name)

    # the point of this batch: recovery actually executed
    assert b_failed == 2, b_failed
    assert retried == 2, retried
    assert measured == 16, measured

    # every retry must have been triggered by a failed first attempt
    assert len(gained) == 2, gained
    assert passed == 16, passed
    assert fs == 0, fs

    print(json.dumps({
        "verdict": "EVOBOT_FIRST_VALID_BATCH",
        "batch_validation": "rc=0 (structure proven, not assumed)",
        "instances": 16,
        "arm_B": "14/16 = 87.5% (64.0-96.5%)",
        "arm_R": "16/16 = 100% (80.6-100%)",
        "paired": "gained 2, lost 0",
        "retries_demonstrably_fired": retried,
        "claims_measured": "%d/16" % measured,
        "false_success": "0/16",
        "false_failure": "%d/16" % ff,
        "caveat": "only 2 instances exercised recovery; R=16/16 is not a 100% claim",
        "evaluator_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
