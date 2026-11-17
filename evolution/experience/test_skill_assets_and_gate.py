#!/usr/bin/env python3
"""Tests for the two pieces that make the chain a SKILL, not a note.

WHY THESE CASES
    Two claims are easy to make and easy to make vacuously:
      "the update passed regression"  - if the gate is never called, or treats "could not
                                         check" as fine, the claim is empty;
      "the lesson became a skill"     - if the asset binds to nothing, or drops a parameter
                                         it cannot map, the "skill" is prose with a name.

    Each test below fails if the corresponding claim becomes vacuous.
"""
import json
import os
import sys

import pytest

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import curate  # noqa: E402
import regression  # noqa: E402
import schema  # noqa: E402
import skill_asset  # noqa: E402
import store  # noqa: E402

BASE = dict(
    origin="AGENT_GENERATED",
    task_family="T13-conditional-two-boxes",
    failure_class="control",
    source_run="setup/acceptance/evobot_recover_n6_20261111/runs/HO-90899d657e68",
    evidence={"clearance_m": 0.05, "place_error_m": 0.00965},
    applicable_when=["two stages land in the same bin"],
    known_invalid_when=["a single stage lands in the bin",
                        "the separation would leave the bin radius"],
    suggested_action="separate same-bin landings by clearance plus measured drift",
)


def entry(**kw):
    args = dict(BASE)
    args.update(kw)
    return schema.make_entry(**args)


def spread_entry(status="CANDIDATE"):
    return entry(action_kind="landing_spacing", consumer="spread_policy",
                 version={"label": "E1", "status": status},
                 effect_spec={"fixture": "t13_two_boxes_one_bin", "operator": "spread_step",
                              "params": {"step_m": 0.090}})


def recovery_entry(status="ACTIVE"):
    return entry(action_kind="recovery_action", consumer="executor_recovery",
                 version={"label": "E2", "status": status},
                 validation={"review_verdict": "ACCEPT", "reviewed_by": "reviewer",
                             "review_ref": "REVIEW.md"},
                 effect_spec={"fixture": "t13_two_boxes_one_bin",
                              "operator": "respread_apply",
                              "params": {"step_m": 0.090, "cluster_m": 0.12}})


# ------------------------------------------------------------- regression gate

def test_gate_keeps_when_nothing_new_fails():
    result = regression.check({"consumer": "spread_policy"},
                              runner=lambda name, acc: (True, "ok"))
    assert result["verdict"] == "KEEP"


def test_gate_reverts_on_a_new_failure():
    def runner(name, acc):
        return (name != "evobot_spacing_fix_20261111", "boom")
    result = regression.check({"consumer": "spread_policy"}, runner=runner)
    assert result["verdict"] == "REVERT"
    assert result["new_failures"] == ["evobot_spacing_fix_20261111"]


def test_a_baselined_failure_is_not_a_reason_to_revert(tmp_path):
    known = tmp_path / "known.json"
    # every verifier in this consumer's pinned subset must be baselined, or the unlisted
    # one counts as a NEW failure - which is the gate working, not a false alarm
    known.write_text(json.dumps({"failures": [
        {"verifier": v} for v in regression.CONSUMER_VERIFIERS["spread_policy"]]}),
        encoding="utf-8")
    result = regression.check({"consumer": "spread_policy"}, known_path=str(known),
                              runner=lambda name, acc: (False, "pre-existing"))
    assert result["verdict"] == "KEEP"
    assert sorted(result["baselined"]) == sorted(
        regression.CONSUMER_VERIFIERS["spread_policy"])


def test_a_missing_baseline_is_unknown_not_a_pass(tmp_path):
    """FAIL CLOSED. This is the bug gate_differential.py documents having had."""
    result = regression.check({"consumer": "spread_policy"},
                              known_path=str(tmp_path / "absent.json"),
                              runner=lambda name, acc: (True, "ok"))
    assert result["verdict"] == "UNKNOWN"
    assert "refusing to guess" in result["why"]


def test_a_timeout_counts_as_a_failure_not_a_pass(monkeypatch):
    import subprocess
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="x", timeout=1)
    monkeypatch.setattr(subprocess, "run", boom)
    ok, detail = regression.run_verifier("evobot_spacing_fix_20261111")
    assert ok is False and "timed out" in detail


def test_gate_activation_requires_accept_and_keep():
    accepted = {"review_verdict": "ACCEPT", "reviewed_by": "r"}
    ok = regression.gate_activation({"consumer": "spread_policy"}, accepted,
                                    runner=lambda n, a: (True, "ok"))
    assert ok["activate"] is True
    refused = regression.gate_activation({"consumer": "spread_policy"},
                                         {"review_verdict": "REJECT"},
                                         runner=lambda n, a: (True, "ok"))
    assert refused["activate"] is False
    failing = regression.gate_activation({"consumer": "spread_policy"}, accepted,
                                         runner=lambda n, a: (False, "boom"))
    assert failing["activate"] is False


def test_activation_refuses_when_the_gate_reverts(tmp_path):
    """The gate must be load-bearing: a REVERT blocks activation even with an ACCEPT."""
    store_path = tmp_path / "s.jsonl"
    ledger_path = tmp_path / "l.jsonl"
    cand = spread_entry()
    store.append(str(store_path), cand)
    real_check = regression.check
    regression.check = lambda *a, **k: {"verdict": "REVERT", "new_failures": ["x"],
                                        "ran": ["x"], "baselined": [], "why": "new failure"}
    try:
        with pytest.raises(schema.EntryError) as exc:
            curate.activate(cand["entry_id"],
                            {"review_verdict": "ACCEPT", "reviewed_by": "r"},
                            store_path=str(store_path), ledger_path=str(ledger_path))
        assert "regression gate refused" in str(exc.value)
    finally:
        regression.check = real_check
    # nothing became ACTIVE
    rows = store.read(str(store_path))
    assert all((r.get("version") or {}).get("status") != "ACTIVE" for r in rows)


def test_activation_records_the_regression_verdict(tmp_path):
    store_path = tmp_path / "s.jsonl"
    ledger_path = tmp_path / "l.jsonl"
    cand = spread_entry()
    store.append(str(store_path), cand)
    succ = curate.activate(cand["entry_id"],
                           {"review_verdict": "ACCEPT", "reviewed_by": "r"},
                           store_path=str(store_path), ledger_path=str(ledger_path))
    assert succ["regression"]["verdict"] == "KEEP"
    assert succ["regression"]["ran"]


def test_a_reject_verdict_does_not_need_the_gate(tmp_path):
    """A rejected branch must still be recorded (DGM), and needs no regression run."""
    store_path = tmp_path / "s.jsonl"
    ledger_path = tmp_path / "l.jsonl"
    cand = spread_entry()
    store.append(str(store_path), cand)
    succ = curate.activate(cand["entry_id"],
                           {"review_verdict": "REJECT", "reviewed_by": "r"},
                           store_path=str(store_path), ledger_path=str(ledger_path),
                           gate=True)
    assert succ["version"]["status"] == "REJECTED"


# ------------------------------------------------------------- skill assets

def test_an_active_entry_compiles_into_a_callable_asset():
    asset = skill_asset.compile_asset(recovery_entry())
    assert asset["callable"]["module"] == "runtime.recovery.recover"
    assert asset["callable"]["function"] == "apply_respread"
    assert asset["callable"]["kwargs"]["spread_step"] == 0.090
    assert skill_asset.callable_exists(asset) is True
    assert asset["code_generated"] is False


def test_a_candidate_cannot_be_compiled():
    with pytest.raises(skill_asset.AssetError):
        skill_asset.compile_asset(recovery_entry(status="CANDIDATE"))


def test_an_entry_without_review_cannot_be_compiled():
    e = recovery_entry()
    e["validation"] = {"review_verdict": "NOT_REVIEWED", "review_ref": None,
                       "reviewed_by": None}
    with pytest.raises(skill_asset.AssetError):
        skill_asset.compile_asset(e)


def test_an_unbound_parameter_is_refused_not_dropped():
    """A silently dropped parameter would make the asset do something else than the entry."""
    e = recovery_entry()
    e["effect_spec"] = dict(e["effect_spec"], params={"step_m": 0.09,
                                                      "unknown_knob": 3})
    with pytest.raises(skill_asset.AssetError) as exc:
        skill_asset.compile_asset(e)
    assert "no binding" in str(exc.value)


def test_an_asset_without_a_guard_is_refused():
    e = recovery_entry()
    e["known_invalid_when"] = []
    with pytest.raises(skill_asset.AssetError) as exc:
        skill_asset.compile_asset(e)
    assert "guard" in str(exc.value)


def test_a_consumer_with_no_callable_binding_is_refused():
    e = entry(action_kind="harness_config", consumer="harness",
              version={"label": "E9", "status": "ACTIVE"},
              effect_spec={"fixture": "t13_two_boxes_one_bin", "operator": "none"},
              validation={"review_verdict": "ACCEPT", "reviewed_by": "r"})
    with pytest.raises(skill_asset.AssetError) as exc:
        skill_asset.compile_asset(e)
    assert "no callable binding" in str(exc.value)


def test_the_asset_calls_the_real_function_and_changes_the_plan():
    """End to end: the compiled asset, invoked, produces the widened spacing."""
    asset = skill_asset.compile_asset(recovery_entry())
    plan = json.load(open(os.path.join(
        WT, "setup/acceptance/evobot_recover_n6_20261111/runs/HO-90899d657e68/plan.json"),
        encoding="utf-8"))
    out = skill_asset.call(asset, plan)
    pts = [(s["place_pose"][0], s["place_pose"][1]) for s in out["stages"]]
    sep = ((pts[0][0] - pts[1][0]) ** 2 + (pts[0][1] - pts[1][1]) ** 2) ** 0.5
    assert sep >= 0.09 - 1e-9, sep


def test_assets_are_append_only_and_versioned(tmp_path):
    path = str(tmp_path / "a.jsonl")
    asset = skill_asset.compile_asset(recovery_entry())
    first = skill_asset.append(path, asset)
    assert first["asset_version"] == 1
    with pytest.raises(skill_asset.AssetError):
        skill_asset.append(path, asset)  # identical asset refused
    changed = dict(asset, guard=list(asset["guard"]) + ["another known failure"])
    changed["asset_sha256"] = schema.digest(
        {k: v for k, v in changed.items() if k != "asset_sha256"})
    second = skill_asset.append(path, changed)
    assert second["asset_version"] == 2
    assert skill_asset.latest(path, asset["asset_id"])["asset_sha256"] ==         changed["asset_sha256"]
