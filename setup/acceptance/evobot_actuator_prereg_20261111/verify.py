#!/usr/bin/env python3
"""Verify the pre-registration exists, predates the change, and is falsifiable."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]


def main():
    reg = json.loads((HERE / "actuator_stall_preregistration.json")
                     .read_text(encoding="utf-8"))
    assert reg["record_kind"] == "EVOBOT_PREREGISTRATION"
    assert reg["registered_before_change"] is True
    assert reg["baseline"]["n"] == 32
    assert reg["baseline"]["r_pass"] == 29
    assert reg["prediction"]["final_pass_rate"].startswith("UNCHANGED")
    assert reg["success_criteria"] and reg["refutation_criteria"]

    # the change must NOT have been applied yet
    src = (WT / "src" / "flexcell" / "flexcell_skills" / "flexcell_skills"
           / "place_server.py").read_text(encoding="utf-8")
    assert src.count("self._gripper.command(self._gripper_open)") == 1
    assert "for release_attempt" not in src

    # the corrected proposal must not repeat the overclaim
    prop = json.loads((HERE / "proposal_actuator_stall_corrected.json")
                      .read_text(encoding="utf-8"))
    assert "UNCHANGED" in prop["expected_effect"]
    assert prop.get("increment_is")

    print(json.dumps({
        "verdict": "EVOBOT_ACTUATOR_RETRY_PREREGISTERED_NOT_APPLIED",
        "baseline": reg["baseline"],
        "predicted_final_pass": reg["prediction"]["final_pass_rate"],
        "increment": prop["increment_is"],
        "overclaim_corrected": True,
        "applied": False,
        "refutation_conditions": len(reg["refutation_criteria"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
