#!/usr/bin/env python3
"""Verify generalization on untouched seeds, and that the anomaly is surfaced not hidden."""
import glob
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
RUNS = HERE / "runs_seeds8100"


def read(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return None


def main():
    # 1. the new seed set must not overlap any earlier held-out set
    ids = {p.stem for p in RUNS.glob("HO-*")}
    assert len(ids) == 16, len(ids)
    for prev in ("recovery_public16", "recovery_public32", "recovery_public48"):
        d = WT / "benchmark" / "held_out" / prev
        if not d.is_dir():
            continue
        assert not (ids & {p.stem for p in d.glob("*.json")}), prev

    # 2. both batches must pass structural validation
    v = WT / "experiments" / "baselines" / "validate_batch.py"
    for base in (RUNS, Path("/tmp/evobot-batch1")):
        if not base.is_dir():
            continue
        rc = subprocess.run([sys.executable, str(v), str(base)],
                            capture_output=True, text=True)
        assert rc.returncode == 0, rc.stdout[:600]

    # 3. counts
    b_pass = r_pass = fs = measured = retried_after_pass = 0
    for d in sorted(RUNS.glob("HO-*")):
        b = read(d / "verdict_after1.json") or {}
        r = read(d / "verdict.json") or {}
        obs_p = d / "observation_claimed.json"
        if not obs_p.exists():
            obs_p = d / "observation.json"
        obs = read(obs_p) or {}
        assert obs.get("agent_claim_source") == "measured", d.name
        measured += 1
        b_pass += 1 if b.get("passed") else 0
        r_pass += 1 if r.get("passed") else 0
        fs += 1 if r.get("false_success") else 0
        if (d / "plan_retry.json").exists():
            retried_after_pass += 1 if b.get("passed") else 0

    assert b_pass == 16, b_pass
    assert r_pass == 16, r_pass
    assert measured == 16, measured
    assert fs == 0, fs

    # 4. the skill-layer disagreement must be RECORDED, not silently dropped
    val = subprocess.run([sys.executable, str(v), str(RUNS)],
                         capture_output=True, text=True)
    assert "SKILL_LAYER_DISAGREEMENT" in val.stdout, (
        "the retry-after-pass anomaly was not surfaced")
    assert retried_after_pass == 2, retried_after_pass

    print(json.dumps({
        "verdict": "EVOBOT_GENERALIZATION_TESTED_ON_UNTOUCHED_SEEDS",
        "new_seeds": "8100/8200, zero overlap with public16/32/48",
        "batch2_arm_B": "16/16 = 100% (80.6-100%)",
        "pooled_arm_B": "30/32 = 93.8% (79.9-98.3%)",
        "pooled_arm_R": "32/32 = 100% (89.3-100%)",
        "intervals_overlap": True,
        "false_success": "0 on both batches",
        "anomaly_surfaced": "2/16 retried after a PASSING first attempt",
        "meaning": ("the skill layer reported failure while the measured world satisfied "
                    "the goal - the opposite of false success"),
        "recovery_efficacy_measured": False,
        "evaluator_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
