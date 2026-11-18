#!/usr/bin/env python3
"""Verify the live recovery call consumes a REVIEWED entry through the ADR-compliant path.

The runtime must NOT import evolution (ADR-002 / skill_boundaries). resolve_live.py runs on
the development side and writes a binding JSON; recovery_driver reads it as plain data. These
tests build that file with the real gate and check the runtime path consumes it faithfully.
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
import resolve_live  # noqa: E402

ASSETS = os.path.join(WT, "setup", "acceptance", "evobot_continual_chain_20261118",
                      "skill_assets.jsonl")
ENTRIES = os.path.join(WT, "setup", "acceptance", "evobot_continual_chain_20261118",
                       "records_v2.jsonl")


def _e2_identity(entries_path):
    rows = [json.loads(l) for l in open(entries_path, encoding="utf-8") if l.strip()]
    entry = [r for r in rows if (r.get("version") or {}).get("label") == "E2"][-1]
    return entry["entry_id"], entry["chain_sha256"]


class Args:
    def __init__(self, binding=None):
        self.experience_binding = binding


def _reviewed_store(tmp_path):
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
    eid, sha = _e2_identity(str(path))
    import review_ledger as chain
    chain.append(str(ledger), {"entry_id": eid, "verdict": "ACCEPT",
                               "reviewed_by": "gate-auditor",
                               "entry_chain_sha256": sha})
    return str(path), str(ledger)


def test_without_a_binding_the_defaults_are_untouched():
    kwargs, why = recovery_driver._experience_kwargs(Args())
    assert kwargs == {}
    assert "frozen baseline defaults" in why


def test_an_unreadable_binding_is_a_refusal(tmp_path):
    kwargs, why = recovery_driver._experience_kwargs(Args(str(tmp_path / "missing.json")))
    assert kwargs == {}
    assert "unreadable" in why


def test_a_reviewed_entry_reaches_the_runtime_through_a_binding_file(tmp_path):
    entries, ledger = _reviewed_store(tmp_path)
    out = tmp_path / "binding.json"
    resolve_live.main(["--asset", ASSETS, "--entries", entries,
                       "--review-ledger", ledger, "--out", str(out)])
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["kwargs"] == {"spread_step": 0.09, "cluster_m": 0.12}
    kwargs, why = recovery_driver._experience_kwargs(Args(str(out)))
    assert kwargs == {"spread_step": 0.09, "cluster_m": 0.12}
    assert "accepted" in why


def test_an_unreviewed_entry_writes_an_empty_binding(tmp_path):
    out = tmp_path / "binding.json"
    resolve_live.main(["--asset", ASSETS, "--entries", ENTRIES, "--out", str(out)])
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["kwargs"] == {}
    kwargs, _ = recovery_driver._experience_kwargs(Args(str(out)))
    assert kwargs == {}


def test_the_respread_call_accepts_the_resolved_kwargs():
    import recover
    import inspect
    params = inspect.signature(recover.apply_respread).parameters
    for key in ("spread_step", "cluster_m"):
        assert key in params
