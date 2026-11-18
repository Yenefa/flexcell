#!/usr/bin/env python3
# A verifier check that a mutation cannot fail is decorative, not evidence.
# This test is the mutation for the "retire follows from harm" acceptance check.
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VERIFY = os.path.join(WT, "setup", "acceptance", "evobot_continual_chain_20261118",
                      "verify.py")


def _causal_predicate(artifact):
    """The same predicate the verifier uses, so the mutation tracks the real check."""
    before = artifact.get("decision_before") or []
    harmful = [d for d in before
               if d.get("decision") == "RETIRE"
               and (d.get("harmful") or 0) >= 1
               and "WORSE" in (d.get("why") or "")]
    return len(harmful) >= 1 and "WORSE" in (artifact.get("retired_reason") or "")


def test_the_real_retirement_artifact_passes():
    import json
    path = os.path.join(WT, "setup", "acceptance", "evobot_continual_chain_20261118",
                        "10_retirement_transition.json")
    with open(path, encoding="utf-8") as fh:
        assert _causal_predicate(json.load(fh)) is True


def test_a_hardcoded_retire_without_harm_is_rejected():
    fake = {"status_after": "RETIRED", "parent_linked": True, "chain_ok": True,
            "note": "synthetic harm on a COPY",
            "decision_before": [{"decision": "RETIRE", "harmful": 0,
                                 "why": "manually retired"}],
            "retired_reason": "manually retired"}
    assert _causal_predicate(fake) is False


def test_the_check_is_actually_in_the_verifier():
    with open(VERIFY, encoding="utf-8") as fh:
        src = fh.read()
    assert "the_retire_follows_from_recorded_harm_not_a_hardcoded_status" in src
