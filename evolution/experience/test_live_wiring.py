#!/usr/bin/env python3
"""Verify the live recovery call can consume a REVIEWED entry without changing defaults.

This connects the last mile: entry -> review gate -> live call kwargs -> result. It is opt-in
and fail-closed, so the frozen baseline default path stays byte-identical.
"""
import json
import os
import sys

import pytest

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "runtime", "recovery"))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import recovery_driver  # noqa: E402
import store  # noqa: E402

ASSETS = os.path.join(WT, "setup", "acceptance", "evobot_continual_chain_20261118",
                      "skill_assets.jsonl")
ENTRIES = os.path.join(WT, "setup", "acceptance", "evobot_continual_chain_20261118",
                       "records_v2.jsonl")


class Args:
    def __init__(self, asset=None, entries=None):
        self.experience_asset = asset
        self.experience_entries = entries
        self.experience_review_ledger = None
        self.experience_observation = None


def test_without_flags_the_call_site_defaults_are_untouched():
    kwargs, why = recovery_driver._experience_kwargs(Args())
    assert kwargs == {}
    assert "frozen baseline defaults" in why


def test_with_unreviewed_flags_the_defaults_are_still_used():
    kwargs, why = recovery_driver._experience_kwargs(Args(ASSETS, ENTRIES))
    assert kwargs == {}
    assert "gate" in why or "defaults" in why


def test_with_an_independently_reviewed_entry_the_kwargs_reach_the_call(tmp_path):
    path = tmp_path / "records.jsonl"
    rows = [json.loads(l) for l in open(ENTRIES, encoding="utf-8") if l.strip()]
    for i, row in enumerate(rows):
        if (row.get("version") or {}).get("label") == "E2":
            row["validation"]["reviewed_by"] = "independent-reviewer"
        row["_nonce"] = i
        for key in ("chain_sha256", "record_sha256", "prev_sha256"):
            row.pop(key, None)
        row["record_sha256"] = store._hash(row)
        store.append(str(path), row)
    ledger = tmp_path / "review_ledger.jsonl"
    eid = [r for r in [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
           if (r.get("version") or {}).get("label") == "E2"][-1]["entry_id"]
    import review_ledger as chain
    chain.append(str(ledger), {"entry_id": eid, "verdict": "ACCEPT",
                               "reviewed_by": "gate-auditor"})
    args = Args(ASSETS, str(path))
    args.experience_review_ledger = str(ledger)
    kwargs, why = recovery_driver._experience_kwargs(args)
    assert kwargs == {"spread_step": 0.09, "cluster_m": 0.12}
    assert "accepted" in why


def test_the_respread_call_accepts_the_resolved_kwargs():
    import recover
    import inspect
    params = inspect.signature(recover.apply_respread).parameters
    for key in ("spread_step", "cluster_m"):
        assert key in params
