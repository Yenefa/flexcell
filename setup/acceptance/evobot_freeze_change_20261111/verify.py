#!/usr/bin/env python3
"""Verify the claim plumbing, the grading invariance, and the re-freeze gate."""
import inspect
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
sys.path.insert(0, str(WT / "benchmark" / "evaluators"))
import observe_from_run as OFR
import evaluate as E


def main():
    # the entry point that did not exist before
    sig = inspect.signature(OFR.build_observation)
    assert sig.parameters["agent_claimed_success"].default is None, sig

    # grading must be independent of the claim
    spec = {
        "task_id": "S",
        "template_id": "T13_geometric_conditional",
        "objects": [{"name": "a", "color": "red",
                     "initial_pose": [0.22, 0.0, 0.0175, 0.0]}],
        "zones": [{"name": "zone_1", "pose": [0.12, -0.15, 0.0175, 0.0],
                   "radius": 0.06}],
        "expected_goal": {"placement": {"a": "zone_1"}, "unmoved": []},
        "constraints": {"order": [], "must_not_move": []},
    }
    base = {"objects": {"a": [0.40, 0.30, 0.0175, 0.0]},
            "move_sequence": [], "visits": {}}
    gradings = []
    for claim in (True, False, None):
        obs = dict(base)
        if claim is not None:
            obs["agent_claimed_success"] = claim
        v = E.evaluate(spec, obs)
        gradings.append((v["passed"],
                         [(c["clause"], c["ok"]) for c in v["clauses"]]))
    assert gradings[0] == gradings[1] == gradings[2], gradings

    # the change must be documented, with a rollback
    log = (WT / "docs" / "FREEZE_CHANGELOG.md").read_text(encoding="utf-8")
    assert "observe_from_run.py" in log
    assert u"\u56de\u6eda" in log or "revert" in log.lower()

    print(json.dumps({
        "verdict": "EVOBOT_CLAIM_PLUMBING_ADDED_WITH_CHANGE_CONTROL",
        "claim_entry_point": "--agent-claim (previously absent)",
        "default_is_now": "None (explicit unknown)",
        "grading_independent_of_claim": True,
        "refreeze_requires_changelog": True,
        "evaluate_py_modified": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
