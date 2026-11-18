#!/usr/bin/env python3
"""Tests for the fail-closed live binding: reviewed experience -> live call parameters.

WHY THIS EXISTS
    The live executor consumer exists (run_batch.sh:107 -> recovery_driver.py:146 ->
    apply_respread) but used the function's DEFAULT kwargs and never looked up an entry. So a
    REVISED entry could never reach the robot. resolve() lets the live call read parameters
    from a compiled asset, but ONLY when every gate re-checks at call time.

    The default path must stay byte-identical: resolve() is opt-in and every refusal returns
    {} so the caller uses exactly the defaults it always used.
"""
import json
import os
import sys

import pytest

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import live_binding  # noqa: E402
import store  # noqa: E402

ASSETS = os.path.join(WT, "setup", "acceptance", "evobot_continual_chain_20261118",
                      "skill_assets.jsonl")
ENTRIES = os.path.join(WT, "setup", "acceptance", "evobot_continual_chain_20261118",
                       "records_v2.jsonl")


def _e2_identity(path):
    """The entry id AND its chain anchor. A review must name both, or it could have been
    pre-generated before the entry was stored."""
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    entry = [r for r in rows if (r.get("version") or {}).get("label") == "E2"][-1]
    return entry["entry_id"], entry["chain_sha256"]


def _rebuilt(tmp_path, reviewer="independent-reviewer"):
    """A fresh store with the same rows, one reviewer field changed, chain rebuilt."""
    path = tmp_path / "records.jsonl"
    rows = [json.loads(line) for line in open(ENTRIES, encoding="utf-8") if line.strip()]
    for i, row in enumerate(rows):
        if (row.get("version") or {}).get("label") == "E2":
            row["validation"]["reviewed_by"] = reviewer
        row["_nonce"] = i
        for key in ("chain_sha256", "record_sha256", "prev_sha256"):
            row.pop(key, None)
        row["record_sha256"] = store._hash(row)
        store.append(str(path), row)
    assert store.verify_chain(str(path))[0]
    return str(path)


def test_no_asset_path_refuses(tmp_path):
    kwargs, why = live_binding.resolve(None, "executor_recovery", ENTRIES)
    assert kwargs == {}
    assert "defaults" in why


def test_missing_asset_file_refuses(tmp_path):
    kwargs, why = live_binding.resolve(str(tmp_path / "none"), "executor_recovery", ENTRIES)
    assert kwargs == {}


def test_a_self_reviewed_entry_is_refused():
    """chain-demo-reviewer is the same run that made the entry: not independent."""
    kwargs, why = live_binding.resolve(ASSETS, "executor_recovery", ENTRIES)
    assert kwargs == {}
    assert "defaults" in why


def test_an_independent_accept_yields_the_asset_kwargs(tmp_path):
    """The ACCEPT must come from a SEPARATE ledger bound to the entry id, not from the
    entry's own validation block, which the same round that authored it wrote."""
    path = _rebuilt(tmp_path)
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    eid, sha = _e2_identity(path)
    ledger = tmp_path / "review_ledger.jsonl"
    import review_ledger as chain
    chain.append(str(ledger), {"entry_id": eid, "verdict": "ACCEPT",
                               "reviewed_by": "gate-auditor",
                               "entry_chain_sha256": sha})
    kwargs, why = live_binding.resolve(ASSETS, "executor_recovery", path,
                                       review_ledger=str(ledger))
    assert kwargs == {"spread_step": 0.09, "cluster_m": 0.12}
    assert "accepted" in why


def test_a_forged_plain_review_line_is_refused(tmp_path):
    """THE MOST IMPORTANT GATE. Before the chain, anyone could append a line naming any
    independent reviewer and the gate would hand parameters to a live robot call."""
    path = _rebuilt(tmp_path)
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    eid, sha = _e2_identity(path)
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(json.dumps({"entry_id": eid, "verdict": "ACCEPT",
                                  "reviewed_by": "any-made-up-name"}) + "\n",
                      encoding="utf-8")
    kwargs, why = live_binding.resolve(ASSETS, "executor_recovery", path,
                                       review_ledger=str(ledger))
    assert kwargs == {}
    assert "intact" in why or "chain" in why


def test_an_edited_chained_review_is_refused(tmp_path):
    """Editing an ACCEPT to REJECT after the fact must be detectable, not silent."""
    import review_ledger as chain
    path = _rebuilt(tmp_path)
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    eid, sha = _e2_identity(path)
    ledger = tmp_path / "ledger.jsonl"
    chain.append(str(ledger), {"entry_id": eid, "verdict": "ACCEPT",
                               "reviewed_by": "gate-auditor",
                               "entry_chain_sha256": sha})
    row = json.loads(open(ledger, encoding="utf-8").readline())
    row["verdict"] = "REJECT"
    ledger.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert live_binding.resolve(ASSETS, "executor_recovery", path,
                                review_ledger=str(ledger))[0] == {}


def test_a_review_of_a_different_claim_does_not_authorise_this_one(tmp_path):
    """THE SHARP CASE. The repo has a real independent ACCEPT for a CONTROL FACT built on
    exactly E2's three evidence files. An independent review of the same evidence for a
    DIFFERENT claim must not authorise E2's actionable spacing recommendation."""
    path = _rebuilt(tmp_path)
    ledger = tmp_path / "review_ledger.jsonl"
    ledger.write_text(json.dumps({
        "entry_id": "T13-recover-clearance-margin", "verdict": "ACCEPT",
        "reviewed_by": "gate-auditor",
        "evidence_files": [
            "setup/acceptance/evobot_recover_n6_20261111/runs/HO-90899d657e68/plan.json"]},
        ensure_ascii=False) + "\n", encoding="utf-8")
    assert live_binding.resolve(ASSETS, "executor_recovery", path,
                                review_ledger=str(ledger))[0] == {}


def test_no_review_ledger_is_a_refusal_even_with_self_attestation(tmp_path):
    """An entry saying reviewed_by=independent-reviewer in its own body is NOT enough: the
    chain proves it was not tampered with, not that anybody independent signed off."""
    path = _rebuilt(tmp_path)
    kwargs, why = live_binding.resolve(ASSETS, "executor_recovery", path)
    assert kwargs == {}
    assert "defaults" in why


def test_a_self_reviewer_name_in_the_ledger_is_refused(tmp_path):
    path = _rebuilt(tmp_path)
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    eid, sha = _e2_identity(path)
    ledger = tmp_path / "review_ledger.jsonl"
    ledger.write_text(json.dumps({"entry_id": eid, "verdict": "ACCEPT",
                                  "reviewed_by": "chain-demo-reviewer"}) + "\n",
                      encoding="utf-8")
    assert live_binding.resolve(ASSETS, "executor_recovery", path,
                                review_ledger=str(ledger))[0] == {}


def test_a_rejected_entry_is_refused(tmp_path):
    path = _rebuilt(tmp_path)
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    p2 = tmp_path / "rejected.jsonl"
    for row in rows:
        if (row.get("version") or {}).get("label") == "E2":
            row["validation"]["review_verdict"] = "REJECT"
        for key in ("chain_sha256", "record_sha256", "prev_sha256"):
            row.pop(key, None)
        row["record_sha256"] = store._hash(row)
        store.append(str(p2), row)
    assert live_binding.resolve(ASSETS, "executor_recovery", str(p2))[0] == {}


def test_a_broken_chain_is_refused(tmp_path):
    path = _rebuilt(tmp_path)
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    eid, sha = _e2_identity(path)
    import review_ledger as chain
    ledger = tmp_path / "review_ledger.jsonl"
    chain.append(str(ledger), {"entry_id": eid, "verdict": "ACCEPT",
                               "reviewed_by": "gate-auditor",
                               "entry_chain_sha256": sha})
    lines = open(path, encoding="utf-8").readlines()
    # tamper a field that actually EXISTS in the record body; changing a key that is not
    # there would leave the hash intact and the test would silently pass for the wrong
    # reason. The effect_spec is part of the hashed body.
    last = json.loads(lines[-1])
    last["effect_spec"]["params"]["cluster_m"] = 999
    lines[-1] = json.dumps(last) + "\n"
    broken = tmp_path / "broken.jsonl"
    broken.write_text("".join(lines), encoding="utf-8")
    assert store.verify_chain(str(broken))[0] is False
    kwargs, why = live_binding.resolve(ASSETS, "executor_recovery", str(broken),
                                       review_ledger=str(ledger))
    assert kwargs == {}
    assert "chain" in why


def test_wrong_consumer_is_refused(tmp_path):
    path = _rebuilt(tmp_path)
    assert live_binding.resolve(ASSETS, "planner", path)[0] == {}


def test_a_non_numeric_kwarg_is_refused(tmp_path):
    """A string where a distance belongs must not reach a live robot call.

    The gate derives kwargs from the ENTRY, not from the compiled asset's cached callable —
    the entry is the reviewed source of truth. So tamper the entry, and rebuild its chain.
    A tampered asset callable alone must NOT change behaviour: that is deliberate, because
    an asset is a derivative and must not be trusted over its entry.
    """
    path = tmp_path / "bad_records.jsonl"
    rows = [json.loads(l) for l in open(ENTRIES, encoding="utf-8") if l.strip()]
    for i, row in enumerate(rows):
        if (row.get("version") or {}).get("label") == "E2":
            row["validation"]["reviewed_by"] = "independent-reviewer"
            row["effect_spec"]["params"]["step_m"] = "0.09"
        row["_nonce"] = i
        for key in ("chain_sha256", "record_sha256", "prev_sha256"):
            row.pop(key, None)
        row["record_sha256"] = store._hash(row)
        store.append(str(path), row)
    assert store.verify_chain(str(path))[0]
    assert live_binding.resolve(ASSETS, "executor_recovery", str(path))[0] == {}


def test_a_tampered_asset_callable_cannot_drive_the_robot(tmp_path):
    """Deliberate: the asset is a derivative. Its cached kwargs must never override the
    reviewed entry, or editing an artifact file would change a live robot call."""
    path = _rebuilt(tmp_path)
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    eid, sha = _e2_identity(path)
    import review_ledger as chain
    ledger = tmp_path / "review_ledger.jsonl"
    chain.append(str(ledger), {"entry_id": eid, "verdict": "ACCEPT",
                               "reviewed_by": "gate-auditor",
                               "entry_chain_sha256": sha})
    a2 = tmp_path / "assets.jsonl"
    asset_rows = [json.loads(l) for l in open(ASSETS, encoding="utf-8") if l.strip()]
    asset_rows[0]["callable"]["kwargs"]["spread_step"] = 999
    a2.write_text("\n".join(json.dumps(r) for r in asset_rows) + "\n", encoding="utf-8")
    kwargs, _ = live_binding.resolve(str(a2), "executor_recovery", path,
                                     review_ledger=str(ledger))
    assert kwargs == {"spread_step": 0.09, "cluster_m": 0.12}


def test_every_declared_invalid_condition_is_accounted_for_on_a_live_path(tmp_path):
    """THE COVERAGE GAP. The live gate used to hard-code two probe ids and missed three of
    E2's four declared invalid conditions (it even looked for spread.single_stage instead of
    respread.single_stage). It then reported 'applicability checked' while blind to them.
    Every declared condition must be either checked or explicitly unprobed."""
    import misuse
    rows = [json.loads(l) for l in open(ENTRIES, encoding="utf-8") if l.strip()]
    entry = [r for r in rows if (r.get("version") or {}).get("label") == "E2"][-1]
    declared = [p.get("probe") for p in (entry.get("invalid_probes") or [])]
    obs = {"plan": {"stages": [{"place_pose": [0.20, 0.0, 0.0175]},
                               {"place_pose": [0.256, 0.0, 0.0175]}]}}
    verdict = live_binding._check_applicability(entry, obs, misuse)
    assert set(verdict["checked"]) | set(verdict["unprobed"]) == set(declared)
    assert not verdict["unprobed"]


def test_an_unknown_declared_probe_refuses_rather_than_passes(tmp_path):
    """A disclaimer with no live check is not a safeguard."""
    import misuse
    entry = {"invalid_probes": [{"probe": "totally.unknown", "condition": "x"}],
             "effect_spec": {"params": {}}}
    obs = {"plan": {"stages": []}}
    verdict = live_binding._check_applicability(entry, obs, misuse)
    assert verdict["fired"] is True
    assert "totally.unknown" in verdict["unprobed"]


def test_an_inapplicable_live_plan_refuses_the_parameters(tmp_path):
    """Objective step 4: check the lesson is not applied where it does not belong. The
    entry's own disclaimer "landings ALREADY meet the spacing contract" is checked against
    the REAL plan, not an archived fixture."""
    import review_ledger as chain
    path = _rebuilt(tmp_path)
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    eid, sha = _e2_identity(path)
    ledger = tmp_path / "ledger.jsonl"
    chain.append(str(ledger), {"entry_id": eid, "verdict": "ACCEPT",
                               "reviewed_by": "gate-auditor",
                               "entry_chain_sha256": sha})
    # 90 mm apart: already meets the 90 mm contract, so respread must NOT fire
    obs = {"plan": {"stages": [{"place_pose": [0.20, 0.0, 0.0175]},
                               {"place_pose": [0.29, 0.0, 0.0175]}]}}
    assert live_binding.resolve(ASSETS, "executor_recovery", path,
                                review_ledger=str(ledger), observation=obs)[0] == {}


def test_an_applicable_live_plan_accepts_the_parameters(tmp_path):
    import review_ledger as chain
    path = _rebuilt(tmp_path)
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    eid, sha = _e2_identity(path)
    ledger = tmp_path / "ledger.jsonl"
    chain.append(str(ledger), {"entry_id": eid, "verdict": "ACCEPT",
                               "reviewed_by": "gate-auditor",
                               "entry_chain_sha256": sha})
    # 56 mm apart: below the 90 mm contract, so the lesson applies
    obs = {"plan": {"stages": [{"place_pose": [0.20, 0.0, 0.0175]},
                               {"place_pose": [0.256, 0.0, 0.0175]}]}}
    assert live_binding.resolve(ASSETS, "executor_recovery", path,
                                review_ledger=str(ledger), observation=obs)[0] == \
        {"spread_step": 0.09, "cluster_m": 0.12}


def test_a_single_stage_is_an_invalid_condition(tmp_path):
    import review_ledger as chain
    path = _rebuilt(tmp_path)
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    eid, sha = _e2_identity(path)
    ledger = tmp_path / "ledger.jsonl"
    chain.append(str(ledger), {"entry_id": eid, "verdict": "ACCEPT",
                               "reviewed_by": "gate-auditor",
                               "entry_chain_sha256": sha})
    obs = {"plan": {"stages": [{"place_pose": [0.20, 0.0, 0.0175]}]}}
    assert live_binding.resolve(ASSETS, "executor_recovery", path,
                                review_ledger=str(ledger), observation=obs)[0] == {}


def test_the_default_function_kwargs_are_unchanged():
    """resolve() never edits the function signature; the fallback is the original default."""
    sys.path.insert(0, os.path.join(WT, "runtime", "recovery"))
    import recover
    import inspect
    sig = inspect.signature(recover.apply_respread)
    assert sig.parameters["spread_step"].default == 0.09
    assert sig.parameters["cluster_m"].default == 0.12


def test_refusal_never_raises(tmp_path):
    """A live path must not die because an experience lookup failed."""
    for consumer in (None, "", "unknown", "executor_recovery"):
        kwargs, why = live_binding.resolve(
            str(tmp_path / "gone"), consumer, str(tmp_path / "gone"))
        assert kwargs == {}
        assert isinstance(why, str)
