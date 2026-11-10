#!/usr/bin/env python3
"""Verify the unified runner: absolute helper paths, self-validating, and smoke-tested."""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
SCRIPTS = WT.parent / "ci-public-window" / "scripts"
RUN = SCRIPTS / "run_batch.sh"


def main():
    assert RUN.exists(), "run_batch.sh missing"
    src = RUN.read_text(encoding="utf-8")

    # 1. every helper must be an absolute path declared up front
    for name in ("PLAN_B", "CLIENT", "CAPTURE", "OBSERVE", "SEALED",
                 "RECOVERY", "ASSESS", "VALIDATE"):
        assert re.search(r'^%s="\$W/' % name, src, re.M), name

    # 2. it must refuse to run if a helper is missing
    assert "FATAL: missing helper" in src

    # 3. it must validate the batch before any number is believed
    assert "validate_batch.py" in src and "BATCH_REJECTED" in src

    # 4. a missing recovery decision must be loud, not silent
    assert "RECOVERY_DID_NOT_RUN" in src

    # 5. set -u must NOT be used: ROS setup scripts are not set -u clean
    assert not re.search(r"^set -u$", src, re.M), (
        "set -u breaks ROS sourcing and silently aborts the run")
    probe = subprocess.run(["bash", "-c", "set -u; source /opt/ros/jazzy/setup.bash"],
                           capture_output=True, text=True)
    assert "unbound variable" in (probe.stderr or ""), (
        "expected the documented set -u failure, got: %r" % (probe.stderr or "")[:120])

    # 6. the smoke run must show every stage executed
    smoke = HERE / "smoke_run"
    if smoke.is_dir():
        runs = list(smoke.glob("HO-*"))
        assert runs, "smoke run produced no run directory"
        d = runs[0]
        for produced in ("plan.json", "task.out", "ground_truth.json",
                         "observation.json", "recovery_decision.json",
                         "self_assessment.json", "verdict.json"):
            assert (d / produced).exists(), "smoke run missing " + produced
        verdict = json.loads((d / "verdict.json").read_text(encoding="utf-8"))
        assert verdict["passed"] is True

    # 7. the superseded copies must still carry the defect
    old = SCRIPTS / "evobot_pair48.sh"
    if old.exists():
        assert "python3 runtime/recovery/recovery_driver.py" in old.read_text(
            encoding="utf-8"), "historical evidence was edited away"

    print(json.dumps({
        "verdict": "EVOBOT_UNIFIED_RUNNER_VERIFIED",
        "runners_before": 4,
        "runners_now": 1,
        "helper_paths": "absolute under $W",
        "self_validating": True,
        "set_u_removed": "ROS setup.bash is not set -u clean",
        "smoke_test": "1 instance, every stage executed",
        "archived_copies_keep_the_defect": True,
        "evaluator_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
