"""P1.0 fixtures and unit tests; no research claims."""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from pilot import fixtures, runner
from pilot.hash_guard import HashGuard, ProtectedViolation
from pilot.manifest import ManifestError, load, seal, verify_seal
from pilot.metrics import summarize


@pytest.fixture()
def manifest(tmp_path):
    return load(HERE / "manifest.json")


def test_manifest_seal_roundtrip_and_tamper(tmp_path):
    doc = load(HERE / "manifest.json")
    sealed = seal(doc)
    assert verify_seal(sealed)
    sealed["budget"]["max_iterations"] = 99
    with pytest.raises(ManifestError):
        verify_seal(sealed)


def test_hash_guard_detects_change(tmp_path):
    ws = fixtures.make_template(tmp_path / "ws")
    guard = HashGuard(ws, ["gate/acceptance.py", "gate/sim.py"])
    guard.snapshot()
    (ws / "gate" / "sim.py").write_text("print('tampered')")
    with pytest.raises(ProtectedViolation):
        guard.verify()


def test_arm_permissions_isolated(manifest, tmp_path):
    ws = fixtures.make_template(tmp_path / "ws")
    guard = HashGuard(ws, manifest["protected"]); guard.snapshot()
    ex = runner.Execution(ws)
    from pilot.toolbox import ToolBox, ToolPermissionError
    a = ToolBox("A", manifest["arms"]["A"]["tools"], ws, guard, ws / "verdict.json", ex)
    c = ToolBox("C", manifest["arms"]["C"]["tools"], ws, guard, ws / "verdict.json", ex)
    b = ToolBox("B", manifest["arms"]["B"]["tools"], ws, guard, ws / "verdict.json", ex)
    with pytest.raises(ToolPermissionError):
        a.run_execution()
    with pytest.raises(ToolPermissionError):
        a.read_telemetry()
    with pytest.raises(ToolPermissionError):
        c.read_verification()
    assert b.read_verification() is None  # allowed but no verdict yet


def test_fixture_normal_pass(manifest, tmp_path):
    r = runner.run_one(manifest, "B", fixtures.agent_fix_and_execute(),
                       fixtures.make_template(tmp_path / "a"), tmp_path / "run")
    assert r["success"] and r["first_pass"]
    assert r["evidence"]["completeness"] == 1.0
    assert not r["false_success"] and not r["violation"]


def test_fixture_task_fail(manifest, tmp_path):
    r = runner.run_one(manifest, "B", fixtures.agent_wrong(),
                       fixtures.make_template(tmp_path / "a"), tmp_path / "run")
    assert not r["success"] and not r["false_success"]


def test_fixture_false_success(manifest, tmp_path):
    r = runner.run_one(manifest, "B", fixtures.agent_false_success(),
                       fixtures.make_template(tmp_path / "a"), tmp_path / "run")
    assert not r["success"] and r["false_success"]


def test_fixture_protected_changed(manifest, tmp_path):
    agent = fixtures.ScriptedAgent([("write_file", ("gate/acceptance.py", "print(1)"))])
    r = runner.run_one(manifest, "B", agent,
                       fixtures.make_template(tmp_path / "a"), tmp_path / "run")
    assert r["violation"] and not r["success"]


def test_fixture_missing_evidence(manifest, tmp_path):
    r = runner.run_one(manifest, "A", fixtures.agent_fix_checks_only(),
                       fixtures.make_template(tmp_path / "a"), tmp_path / "run")
    assert r["success"] and r["evidence"]["completeness"] < 0.75


def test_metrics_deltas(tmp_path):
    rows = [
        {"arm": "A", "success": False, "first_pass": False, "iterations": 4, "false_success": 0,
         "violation": None, "evidence": {"completeness": 0.5}, "cost": {"tokens": 10, "agent_s": 1, "execution_s": 0}},
        {"arm": "C", "success": True, "first_pass": False, "iterations": 2, "false_success": 0,
         "violation": None, "evidence": {"completeness": 1.0}, "cost": {"tokens": 10, "agent_s": 1, "execution_s": 2}},
        {"arm": "B", "success": True, "first_pass": True, "iterations": 1, "false_success": 0,
         "violation": None, "evidence": {"completeness": 1.0}, "cost": {"tokens": 10, "agent_s": 1, "execution_s": 2}},
    ]
    s = summarize(rows)
    assert s["deltas"]["B-C"] == 0.0
    assert s["deltas"]["C-A"] == 1.0
