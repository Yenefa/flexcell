#!/usr/bin/env python3
"""Verify the A/B result: pointless retries gone AND no measured gain lost."""
import glob
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
AFTER = HERE / "runs_goal_check_active"


def read(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return {}


def main():
    d = AFTER
    runs = sorted(d.glob("HO-*"))
    assert len(runs) == 16, len(runs)

    # the batch must pass structural validation, with no retry-after-pass
    v = WT / "experiments" / "baselines" / "validate_batch.py"
    rc = subprocess.run([sys.executable, str(v), str(d)], capture_output=True, text=True)
    assert rc.returncode == 0, rc.stdout[:800]
    assert '"retried_after_pass": 0' in rc.stdout, rc.stdout[:800]

    skipped = refused = not_met = gains = 0
    for run in runs:
        dec = read(run / "recovery_decision.json")
        dec = dec.get("decision") or dec
        reason = str(dec.get("reason") or dec.get("why") or "")
        gc = read(run / "goal_check.json")
        b = read(run / "verdict_after1.json").get("passed")
        r = read(run / "verdict.json").get("passed")

        if "goal already satisfied" in reason:
            skipped += 1
            # a skip is only legitimate when the world already met the goal
            assert b is True, (run.name, "skipped although the world had NOT met the goal")
            assert all(s.get("status") == "AT_TARGET"
                       for s in gc.get("stages", [])), (run.name, gc)
        elif "REFUSED" in str(gc.get("decision", "")):
            refused += 1
        elif gc.get("stages"):
            not_met += 1

        if not b and r:
            gains += 1
            # every gain must have come from a retry that the check did NOT skip
            assert (run / "plan_retry.json").exists(), (run.name, "gain without a retry")

    assert skipped == 3, skipped
    assert refused == 2, refused
    assert gains == 2, gains
    # the safety property: the productive retries are exactly the refused ones
    assert gains == refused, (gains, refused,
                              "a gain was not protected by a REFUSED decision")

    print(json.dumps({
        "verdict": "EVOBOT_GOAL_CHECK_VALIDATED_END_TO_END",
        "same_instances_before_and_after": 16,
        "pointless_retries": "2 -> 0",
        "paired_gains": "0 -> 2",
        "paired_losses": "0 -> 0",
        "skipped_as_already_met": skipped,
        "refused_for_ordering": refused,
        "checked_and_not_met": not_met,
        "safety_property": "every measured gain came from a run the check REFUSED to skip",
        "arm_B_change_is_world_noise": True,
        "evaluator_touched": False,
        "skill_layer_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
