#!/usr/bin/env python3
# A RETIRED or REVISED asset cannot drive the robot: the docstring claims it, but this was
# never tested. A compiled asset is a derivative; if its entry is superseded on the lineage,
# the live gate must refuse it even though the asset file still names a now-old entry_id.
import json
import os
import sys

import pytest

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import live_binding  # noqa: E402
import review_ledger  # noqa: E402
import store  # noqa: E402

ASSETS = os.path.join(WT, "setup", "acceptance", "evobot_continual_chain_20261118",
                      "skill_assets.jsonl")
ENTRIES = os.path.join(WT, "setup", "acceptance", "evobot_continual_chain_20261118",
                       "records_v2.jsonl")


def _e2():
    rows = [json.loads(l) for l in open(ENTRIES, encoding="utf-8") if l.strip()]
    return [r for r in rows if (r.get("version") or {}).get("label") == "E2"][-1]


def _base_store(path, e2):
    rows = [json.loads(l) for l in open(ENTRIES, encoding="utf-8") if l.strip()]
    for i, r in enumerate(rows):
        if r.get("entry_id") == e2["entry_id"]:
            r["validation"]["reviewed_by"] = "independent-reviewer"
        r["_nonce"] = i
        for k in ("chain_sha256", "record_sha256", "prev_sha256"):
            r.pop(k, None)
        r["record_sha256"] = store._hash(r)
        store.append(str(path), r)
    return str(path)


def _accept_ledger(tmp_path, e2, store_path):
    current = [r for r in store.read(store_path)
               if r.get("entry_id") == e2["entry_id"]][0]
    p = str(tmp_path / "ledger.jsonl")
    review_ledger.append(p, {"entry_id": e2["entry_id"], "verdict": "ACCEPT",
                             "reviewed_by": "gate-auditor",
                             "entry_chain_sha256": current["chain_sha256"]})
    return p


def test_asset_drives_call_while_entry_is_the_latest(tmp_path):
    e2 = _e2()
    sp = _base_store(tmp_path / "s.jsonl", e2)
    led = _accept_ledger(tmp_path, e2, sp)
    kwargs, _ = live_binding.resolve(ASSETS, "executor_recovery", sp, review_ledger=led)
    assert kwargs == {"spread_step": 0.09, "cluster_m": 0.12}


def _append_successor(path, e2, status):
    successor = json.loads(json.dumps(e2))
    for k in ("chain_sha256", "record_sha256", "prev_sha256"):
        successor.pop(k, None)
    successor["_nonce"] = "successor-%s" % status
    successor["version"] = dict(e2["version"], status=status,
                                parent_entry_id=e2["entry_id"])
    successor["entry_id"] = "successor-" + status
    successor["record_sha256"] = store._hash(successor)
    store.append(path, successor)
    return successor


def test_a_retired_successor_on_the_lineage_refuses_the_old_asset(tmp_path):
    e2 = _e2()
    sp = _base_store(tmp_path / "s.jsonl", e2)
    led = _accept_ledger(tmp_path, e2, sp)
    _append_successor(sp, e2, "RETIRED")
    kwargs, why = live_binding.resolve(ASSETS, "executor_recovery", sp, review_ledger=led)
    assert kwargs == {}
    assert "defaults" in why or "no asset" in why


def test_a_revised_successor_on_the_lineage_refuses_the_old_asset(tmp_path):
    e2 = _e2()
    sp = _base_store(tmp_path / "s.jsonl", e2)
    led = _accept_ledger(tmp_path, e2, sp)
    _append_successor(sp, e2, "ACTIVE")
    kwargs, why = live_binding.resolve(ASSETS, "executor_recovery", sp, review_ledger=led)
    assert kwargs == {}


def test_a_real_lifecycle_retire_refuses_the_old_asset(tmp_path):
    import lifecycle
    e2 = _e2()
    sp = _base_store(tmp_path / "s.jsonl", e2)
    led = _accept_ledger(tmp_path, e2, sp)
    usage = str(tmp_path / "usage.jsonl")
    retired = lifecycle.retire(e2["entry_id"], "synthetic harm",
                               store_path=sp, ledger_path=usage)
    assert retired["version"]["status"] == "RETIRED"
    assert retired["version"]["label"] == e2["version"]["label"]
    kwargs, _ = live_binding.resolve(ASSETS, "executor_recovery", sp, review_ledger=led)
    assert kwargs == {}
