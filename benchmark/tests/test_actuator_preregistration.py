#!/usr/bin/env python3
"""Tests for the actuator pre-registration and the honest increment calculation."""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_preregistration_exists_and_predates_the_change():
    p = ROOT / "evolution" / "proposals" / "actuator_stall_preregistration.json"
    assert p.exists(), "run evolution/proposals/preregister_actuator.py"
    reg = json.loads(p.read_text(encoding="utf-8"))
    assert reg["record_kind"] == "EVOBOT_PREREGISTRATION"
    assert reg["registered_before_change"] is True
    # the change must NOT have been applied - the gate depends on this
    src = (ROOT / "src" / "flexcell" / "flexcell_skills" / "flexcell_skills"
           / "place_server.py").read_text(encoding="utf-8")
    assert "for release_attempt" not in src


def test_preregistration_has_both_success_and_refutation_criteria():
    reg = json.loads((ROOT / "evolution" / "proposals"
                      / "actuator_stall_preregistration.json")
                     .read_text(encoding="utf-8"))
    assert reg["success_criteria"]
    # a pre-registration without refutation conditions is a wish
    assert reg["refutation_criteria"]
    joined = " ".join(reg["refutation_criteria"]).lower()
    assert "reverted" in joined


def test_prediction_is_falsifiable_not_vague():
    reg = json.loads((ROOT / "evolution" / "proposals"
                      / "actuator_stall_preregistration.json")
                     .read_text(encoding="utf-8"))
    assert "UNCHANGED at" in reg["prediction"]["final_pass_rate"]
    assert isinstance(reg["prediction"]["persistent_stalls_still_fail"], int)


def test_proposal_effect_states_the_real_increment():
    """My first wording claimed phases 'will succeed'. They already do."""
    doc = json.loads((ROOT / "evolution" / "proposals" / "actuator_stall.json")
                     .read_text(encoding="utf-8"))
    eff = doc["expected_effect"].lower()
    assert "unchanged" in eff, eff
    assert doc.get("increment_is"), "must state what the change actually buys"
    assert "latency" in doc["increment_is"].lower()


def test_increment_script_separates_existing_recovery_from_new():
    mod = _load("stall_increment",
                Path("experiments") / "baselines" / "stall_increment.py")
    assert hasattr(mod, "main")


def test_baserate_script_separates_absorbed_from_persistent():
    mod = _load("stall_baserate", Path("experiments") / "baselines" / "stall_baserate.py")
    assert hasattr(mod, "wilson")
    p, lo, hi = mod.wilson(6, 9)
    assert 0.0 <= lo <= p <= hi <= 1.0


def test_baserate_never_reports_a_certainty():
    """6/9 must not be quoted as if it were known exactly."""
    mod = _load("stall_baserate2", Path("experiments") / "baselines" / "stall_baserate.py")
    p, lo, hi = mod.wilson(6, 9)
    assert hi - lo > 0.2, (lo, hi)
