"""P1.0 fixtures and unit tests; no research claims."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from pilot import fixtures, runner, tasks
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


def _contracts_src():
    return HERE.parents[1] / "src/flexcell/flexcell_skills/flexcell_skills/contracts/composite.py"


def test_ta2_initial_plan_rejected(manifest, tmp_path):
    ws = tasks.build(tmp_path / "ws", _contracts_src())
    import subprocess
    proc = subprocess.run([sys.executable, "gate/acceptance.py"], cwd=ws, capture_output=True, text=True)
    assert proc.returncode != 0
    assert "\"error_code\": 60" in proc.stdout


def test_ta2_scripted_fix_passes(manifest, tmp_path):
    import json
    contracts = _contracts_src()
    plan = json.loads((tasks.build(tmp_path / "tpl", contracts) / "plan.json").read_text())
    plan["clearance_m"] = 0.06
    good = json.dumps(plan)
    agent = fixtures.ScriptedAgent([("write_file", ("plan.json", good))])
    res = runner.run_one(manifest, "B", agent, tasks.build(tmp_path / "tpl2", contracts), tmp_path / "run",
                         meta={"task": "T-A-v2"},
                         protected=manifest["task_protected"]["T-A-v2"])
    assert res["success"]


def _hidden_robot(tmp_path):
    hidden = tmp_path / "hidden"
    hidden.mkdir(exist_ok=True)
    path = hidden / "robot.json"
    path.write_text(json.dumps({"max_reach_m": 0.30, "base": [0.0, 0.0, 0.0]}))
    return {"PILOT_ROBOT": str(path)}


def test_tc1_initial_plan_unreachable_on_execution(manifest, tmp_path):
    env = _hidden_robot(tmp_path)
    ws = tasks.build_tc(tmp_path / "ws", _contracts_src())
    proc = subprocess.run([sys.executable, "gate/acceptance.py"], cwd=ws,
                          capture_output=True, text=True, env={**os.environ, **env})
    assert proc.returncode != 0
    assert "\"error_code\": 71" in proc.stdout


def test_tc1_scripted_execution_fix_passes(manifest, tmp_path):
    env = _hidden_robot(tmp_path)
    contracts = _contracts_src()
    plan = json.loads((tasks.build_tc(tmp_path / "tpl", contracts) / "plan.json").read_text())
    plan["stages"][0]["destination"] = [0.20, 0.15, 0.0175]
    agent = fixtures.ScriptedAgent([("write_file", ("plan.json", json.dumps(plan))),
                                    ("run_execution", ())])
    res = runner.run_one(manifest, "C", agent, tasks.build_tc(tmp_path / "tpl2", contracts),
                         tmp_path / "run", meta={"task": "T-C-v1"},
                         protected=manifest["task_protected"]["T-C-v1"],
                         execution_factory=tasks.TCExecution, extra_env=env)
    assert res["success"]
    assert res["evidence"]["completeness"] == 1.0


def test_tb1_initial_fails_at_second_stage(manifest, tmp_path):
    env = _hidden_robot(tmp_path)
    ws = tasks.build_tb(tmp_path / "ws", _contracts_src())
    proc = subprocess.run([sys.executable, "gate/acceptance.py"], cwd=ws,
                          capture_output=True, text=True, env={**os.environ, **env})
    assert proc.returncode != 0
    assert "\"failed_stage\": \"s2\"" in proc.stdout


def test_tb1_scripted_fix_passes(manifest, tmp_path):
    env = _hidden_robot(tmp_path)
    contracts = _contracts_src()
    plan = json.loads((tasks.build_tb(tmp_path / "tpl", contracts) / "plan.json").read_text())
    plan["stages"][1]["destination"] = [0.15, 0.10, 0.0175]
    agent = fixtures.ScriptedAgent([("write_file", ("plan.json", json.dumps(plan))),
                                    ("run_execution", ())])
    res = runner.run_one(manifest, "C", agent, tasks.build_tb(tmp_path / "tpl2", contracts),
                         tmp_path / "run", meta={"task": "T-B-v1"},
                         protected=manifest["task_protected"]["T-B-v1"],
                         execution_factory=tasks.TCExecution, extra_env=env)
    assert res["success"]
