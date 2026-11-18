#!/usr/bin/env python3
"""Tests for the two steps the chain was missing: misuse checking and retirement.

WHY THESE CASES
    Both modules guard claims that are easy to make vacuously:
      "we checked it will not be misused"  - true if the check never runs, or runs on an
                                             empty probe list, or cannot see its own input;
      "harmful entries get retired"        - true if the verdict is computed and discarded,
                                             or if retirement re-fires every pass because
                                             entry_id changes with version.status.

    Every test below fails if the corresponding claim becomes vacuous again.
"""
import json
import os
import sys

import pytest

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import curate  # noqa: E402
import lifecycle  # noqa: E402
import misuse  # noqa: E402
import schema  # noqa: E402
import store  # noqa: E402

CONDS = ["a single stage lands in the bin (nothing to separate)",
         "the separation would leave the bin radius"]


def make(**kw):
    base = dict(
        origin="AGENT_GENERATED", task_family="T13-conditional-two-boxes",
        failure_class="control",
        source_run="setup/acceptance/evobot_recover_n6_20261111/runs/HO-90899d657e68",
        evidence={"clearance_m": 0.05, "place_error_m": 0.00965},
        applicable_when=["two stages land in the same bin"],
        known_invalid_when=CONDS,
        suggested_action="separate same-bin landings",
        action_kind="landing_spacing", consumer="spread_policy",
        effect_spec={"fixture": "t13_two_boxes_one_bin", "operator": "spread_step",
                     "params": {"step_m": 0.090}},
        version={"label": "E1", "status": "CANDIDATE"},
        invalid_probes=[{"condition": CONDS[0], "probe": "spread.single_stage"},
                        {"condition": CONDS[1], "probe": "spread.narrow_bin"}],
    )
    base.update(kw)
    return schema.make_entry(**base)


# ---------------------------------------------------------------- misuse

def test_probed_conditions_are_blocked():
    result = misuse.check(make())
    assert result["verdict"] == "BLOCKED", result
    assert len(result["probed"]) == 2
    assert all(p["outcome"] in ("REFUSED", "INERT") for p in result["probed"])


def test_an_entry_with_no_probes_is_unprobed_not_safe():
    """The exact vacuity this module exists to prevent."""
    e = make(known_invalid_when=[CONDS[0]], invalid_probes=[])
    result = misuse.check(e)
    assert result["verdict"] == "UNPROBED"
    assert "not a safeguard" in result["why"]


def test_an_unknown_probe_id_is_unprobed_not_guessed():
    e = make(invalid_probes=[{"condition": c, "probe": "does.not.exist"} for c in CONDS])
    result = misuse.check(e)
    assert result["verdict"] == "UNPROBED"
    assert len(result["unprobed"]) == 2


def test_a_probe_that_fires_where_it_must_not_reports_misusable(monkeypatch):
    """If a consumer ever changes behaviour in a disclaimed condition, say so."""
    monkeypatch.setitem(misuse.PROBES, "spread.single_stage",
                        lambda params: ("APPLIED", "changed the result"))
    result = misuse.check(make())
    assert result["verdict"] == "MISUSABLE"
    assert len(result["misused"]) == 1


# ------------------------------------------------- the misuse that was a real defect
#
# This probe did not confirm a design, it found a bug. apply_respread widened every
# cluster within cluster_m, so a plan sitting at exactly the 90 mm contract was rotated
# onto the other axis: 94 of 127 touched plans on the archive needed no change and were
# displaced anyway, 64 mm in the T03 case.

def _recover():
    """Import the recovery module the same way the runtime does."""
    sys.path.insert(0, os.path.join(WT, "runtime", "recovery"))
    import recover
    return recover


def test_a_plan_already_at_the_contract_is_left_alone():
    recover = _recover()
    step = 0.090
    plan = {"stages": [
        {"stage_id": "a-0", "object_name": "a", "place_pose": [0.075, -0.15, 0.0175]},
        {"stage_id": "b-1", "object_name": "b",
         "place_pose": [0.075 + step, -0.15, 0.0175]},
    ]}
    before = json.dumps(plan, sort_keys=True)
    out = recover.apply_respread(plan, spread_step=step, cluster_m=0.12,
                                 avoid=[[0.22, 0.0], [0.20, -0.18]])
    assert out["stages"] == plan["stages"], (
        "respread displaced a plan that already met the contract")
    assert json.dumps(plan, sort_keys=True) == before


def test_a_plan_below_the_contract_still_gets_widened():
    """The inert rule must not disable the real case it exists for."""
    recover = _recover()
    plan = {"stages": [
        {"stage_id": "a-0", "object_name": "a", "place_pose": [0.092, -0.15, 0.0175]},
        {"stage_id": "b-1", "object_name": "b", "place_pose": [0.148, -0.15, 0.0175]},
    ]}
    out = recover.apply_respread(plan, spread_step=0.090, cluster_m=0.12,
                                 avoid=[[0.22, 0.0], [0.20, -0.18]])
    assert out["recovered"] is True
    assert out["stages"] != plan["stages"]


def test_the_already_satisfied_probe_reports_inert():
    """If this ever reports APPLIED, the needless-displacement regression is back."""
    outcome, detail = misuse.PROBES["spacing.already_satisfied"](
        {"step_m": 0.090, "cluster_m": 0.12})
    assert outcome == "INERT", detail


def test_schema_refuses_a_partial_probe_list():
    """Declaring three conditions and probing one would make all three look checked."""
    e = make()
    body = dict(e)
    body["invalid_probes"] = e["invalid_probes"][:1]
    body["entry_id"] = schema.digest(schema._body(body))
    problems = schema.validate(body)
    assert any("no probe" in p for p in problems), problems


def test_schema_refuses_a_probe_without_its_condition():
    e = make()
    body = dict(e)
    body["invalid_probes"] = [{"probe": "spread.single_stage"},
                              {"condition": CONDS[1], "probe": "spread.narrow_bin"}]
    body["entry_id"] = schema.digest(schema._body(body))
    problems = schema.validate(body)
    assert any("needs the condition" in p for p in problems), problems


def test_activation_refuses_an_unprobed_entry(tmp_path):
    store_path = tmp_path / "s.jsonl"
    ledger_path = tmp_path / "l.jsonl"
    e = make(known_invalid_when=[CONDS[0]], invalid_probes=[])
    store.append(str(store_path), e)
    with pytest.raises(schema.EntryError) as exc:
        curate.activate(e["entry_id"],
                        {"review_verdict": "ACCEPT", "reviewed_by": "r"},
                        store_path=str(store_path), ledger_path=str(ledger_path))
    assert "misuse check refused" in str(exc.value)


def test_activation_records_the_misuse_verdict(tmp_path):
    store_path = tmp_path / "s.jsonl"
    ledger_path = tmp_path / "l.jsonl"
    e = make()
    store.append(str(store_path), e)
    succ = curate.activate(e["entry_id"],
                           {"review_verdict": "ACCEPT", "reviewed_by": "r"},
                           store_path=str(store_path), ledger_path=str(ledger_path))
    assert succ["misuse_check"]["verdict"] == "BLOCKED"
    assert succ["misuse_check"]["probed"] == 2


# ---------------------------------------------------------------- lifecycle

def _active(tmp_path, name="s"):
    store_path = tmp_path / (name + ".jsonl")
    ledger_path = tmp_path / (name + "_l.jsonl")
    e = make()
    store.append(str(store_path), e)
    return store_path, ledger_path, curate.activate(
        e["entry_id"], {"review_verdict": "ACCEPT", "reviewed_by": "r"},
        store_path=str(store_path), ledger_path=str(ledger_path))


def _harm(ledger_path, entry_id, run):
    import ledger
    ledger.append(str(ledger_path), entry_id, "APPLIED", run_id=run)
    ledger.append(str(ledger_path), entry_id, "OUTCOME", run_id=run, outcome="WORSE")


def test_never_used_entry_is_kept(tmp_path):
    store_path, ledger_path, succ = _active(tmp_path)
    decisions = lifecycle.review(str(store_path), str(ledger_path))
    assert [d["decision"] for d in decisions] == ["KEEP"]


def test_helpful_entry_is_kept(tmp_path):
    store_path, ledger_path, succ = _active(tmp_path)
    import ledger
    ledger.append(str(ledger_path), succ["entry_id"], "APPLIED", run_id="r1")
    ledger.append(str(ledger_path), succ["entry_id"], "OUTCOME", run_id="r1",
                  outcome="IMPROVED")
    assert lifecycle.review(str(store_path), str(ledger_path))[0]["decision"] == "KEEP"


def test_a_harmful_application_makes_the_entry_retirable(tmp_path):
    store_path, ledger_path, succ = _active(tmp_path)
    _harm(ledger_path, succ["entry_id"], "r1")
    d = lifecycle.review(str(store_path), str(ledger_path))[0]
    assert d["decision"] == "RETIRE" and d["effect"] == "used_harmful"


def test_retirement_appends_a_successor_and_keeps_the_harmful_version(tmp_path):
    store_path, ledger_path, succ = _active(tmp_path)
    _harm(ledger_path, succ["entry_id"], "r1")
    result = lifecycle.apply(str(store_path), str(ledger_path))
    assert len(result["retired"]) == 1
    rows = store.read(str(store_path))
    # the harmful ACTIVE record is still there - append-only
    assert any(r["entry_id"] == succ["entry_id"]
               and r["version"]["status"] == "ACTIVE" for r in rows)
    new_id, head = lifecycle.latest(rows, succ["entry_id"])
    assert head["version"]["status"] == "RETIRED"
    assert head["version"]["parent_entry_id"] == succ["entry_id"]
    assert "WORSE" in head["version"]["retired_reason"]
    ok, msg = store.verify_chain(str(store_path))
    assert ok, msg


def test_retirement_is_idempotent_across_passes(tmp_path):
    """The first version re-retired on every pass because entry_id changes per version."""
    store_path, ledger_path, succ = _active(tmp_path)
    _harm(ledger_path, succ["entry_id"], "r1")
    first = lifecycle.apply(str(store_path), str(ledger_path))
    second = lifecycle.apply(str(store_path), str(ledger_path))
    assert len(first["retired"]) == 1
    assert second["retired"] == []
    retired_records = [r for r in store.read(str(store_path))
                       if (r.get("version") or {}).get("status") == "RETIRED"]
    assert len(retired_records) == 1


def test_a_retired_entry_is_no_longer_retrievable(tmp_path):
    import retrieve
    store_path, ledger_path, succ = _active(tmp_path)
    _harm(ledger_path, succ["entry_id"], "r1")
    lifecycle.apply(str(store_path), str(ledger_path))
    kept, report = retrieve.retrieve("spread_policy", store_path=str(store_path),
                                     ledger_path=str(ledger_path), record=False)
    assert kept == []
    assert any("not ACTIVE" in r["why"] for r in report["refused"])


def test_a_superseded_record_does_not_resurrect_the_lineage(tmp_path):
    """The old ACTIVE record stays on disk; the lineage is what says it is over."""
    store_path, ledger_path, succ = _active(tmp_path)
    rows = store.read(str(store_path))
    superseded = lifecycle.superseded_ids(rows)
    assert succ["entry_id"] not in superseded  # the live head is not superseded
    _harm(ledger_path, succ["entry_id"], "r1")
    lifecycle.apply(str(store_path), str(ledger_path))
    rows = store.read(str(store_path))
    assert succ["entry_id"] in lifecycle.superseded_ids(rows)
