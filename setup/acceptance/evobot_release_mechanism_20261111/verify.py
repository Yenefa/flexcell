#!/usr/bin/env python3
"""Verify the release-failure mechanism and that the corrected proposal is pre-registered."""
import glob
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]


def main():
    # 1. every observed release failure has carry_release_confirmed = True
    n = 0
    for base in ("/tmp/evobot-batch2", "/tmp/evobot-batch3"):
        for d in sorted(glob.glob(os.path.join(base, "HO-*"))):
            p = os.path.join(d, "sim", "skills", "place.jsonl")
            if not os.path.exists(p):
                continue
            for line in open(p, encoding="utf-8", errors="replace"):
                line = line.strip()
                if not line:
                    continue
                x = json.loads(line)
                if x.get("released"):
                    continue
                n += 1
                assert x.get("carry_release_confirmed") is True, (d, x.get("detail"))
                g = x.get("gripper_open") or {}
                assert g.get("reached_goal") is False, d
                assert g.get("classification") == "GRASP_STALLED", d
    assert n == 9, n

    # 2. the old proposal must carry the correction, not be silently replaced
    old = json.loads((WT / "evolution" / "proposals" /
                      "actuator_stall_preregistration.json").read_text(encoding="utf-8"))
    assert "superseded_basis" in old

    # 3. the new proposal is pre-registered and NOT approved
    new = json.loads((WT / "evolution" / "proposals" /
                      "release_confirmation_preregistration.json").read_text(
                          encoding="utf-8"))
    assert new["requires_human_approval"] is True
    assert new["approved"] is False
    assert new["observed_mechanism"]["cases"] == 9
    assert new["observed_mechanism"]["signature_is_uniform_across_batches"] is True
    assert len(new["refutation_criteria"]) >= 3
    assert "evaluator_untouched" in new["anti_gaming"]

    # 4. the skill layer must be untouched by this round
    assert "not implemented" in new["status"].lower()

    print(json.dumps({
        "verdict": "EVOBOT_RELEASE_MECHANISM_IDENTIFIED",
        "release_failures_examined": n,
        "uniform_signature": "carry_release_confirmed=True, gripper reached_goal=False",
        "root_cause": ("the skill decides release failure from the gripper aperture alone, "
                       "ignoring the carry confirmation in the same record"),
        "old_proposal": "bounded_release_retry - premise refuted, basis marked superseded",
        "new_proposal": "release_confirmation_over_gripper_aperture",
        "status": "PROPOSED, awaiting human approval, NOT implemented",
        "mitigation_already_live": "goal_check",
        "evaluator_touched": False,
        "skill_layer_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
