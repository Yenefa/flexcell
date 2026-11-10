#!/usr/bin/env python3
"""Verify the FIRST non-retrospective proposal: real gap, real evidence, gated, unapplied."""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, WT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gen_mod = load("gen", "evolution/proposals/generate.py")
chk_mod = load("chk", "evolution/proposals/check_applied.py")


def main():
    doc = json.loads((HERE / "proposal_actuator_stall.json").read_text(encoding="utf-8"))
    assert doc["signature"] == "actuator_stall"
    assert doc["occurrences"] >= 20, doc["occurrences"]
    assert doc["requires_human_approval"] is True
    assert doc["rollback"]
    assert "place_server.py" in doc["files"][0]

    # the proposal must be NEW WORK, not a reconstruction of something already done
    label, detail = chk_mod.check_actuator_stall()
    assert label == "WOULD_FIX", (label, detail)

    # and the code must really still issue the release exactly once
    src = (WT / "src" / "flexcell" / "flexcell_skills" / "flexcell_skills"
           / "place_server.py").read_text(encoding="utf-8")
    assert src.count("self._gripper.command(self._gripper_open)") == 1

    # it was NOT applied: the approval gate must be respected
    assert "for release_attempt" not in src

    print(json.dumps({
        "verdict": "EVOBOT_FIRST_WOULD_FIX_PROPOSAL_VERIFIED",
        "signature": doc["signature"],
        "evidence_occurrences": doc["occurrences"],
        "behavioural_label": label,
        "human_approval_required": True,
        "applied": False,
        "level5": "NOT ACHIEVED (proposal unapproved, unapplied, unmeasured)",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
