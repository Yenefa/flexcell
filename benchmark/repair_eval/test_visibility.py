#!/usr/bin/env python3
"""Visibility boundary tests: the no-feedback condition must not be able to peek.

WHY: issue #249 exists because the W5 tool layer authorised by tool *name* while
w5.py:178 wrote the judge's verdict into the candidate workspace, so the
"no feedback" arm could simply read verdict.json.  These tests drive the boundary
through the negative cases the issue lists -- reserved names, "..", absolute
paths, symlink aliases, hard links, the feedback tools, inherited artefacts --
and through the positive cases that prove the refusal is policy-shaped rather
than hardcoded.

Everything here is offline and standard-library only: no ROS, no simulator, no
model call, no network.
"""
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from benchmark.repair_eval import visibility as vis  # noqa: E402

POLICY_PATH = ROOT / "benchmark" / "repair_eval" / "visibility_policy.json"

SOURCE = '''"""Recovery decision used by the workcell executor."""


def next_action(outcome, error_code, budget):
    if outcome == 0:
        return "DONE"
    return "ABORT"
'''

VERDICT = {
    "passed": False,
    "returncode": 1,
    "error_code": 30,
    "failed_stage": "grasp",
    "detail": "target scenario aborted",
    "answer": "LEAK_MARKER",
}

OWN_FEEDBACK = json.dumps({
    "returncode": 1,
    "passed": False,
    "stdout": "run-b: expected OBSERVE, got ABORT",
    "stderr": "",
    "secret": "SEALED-BY-PROJECTION",
}, sort_keys=True) + "\n"

OTHER_FEEDBACK = json.dumps({
    "returncode": 1,
    "passed": False,
    "stdout": "run-a: unrelated failure",
    "stderr": "",
}, sort_keys=True) + "\n"


# --------------------------------------------------------------------- fixtures
def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture(scope="module")
def policy():
    return vis.load_policy(POLICY_PATH)


def make_run(tmp_path, *, telemetry=False, stale=False, link=None):
    """One run tree: candidate / verdict / hidden, plus a fixed other run."""
    run = tmp_path / "run-b"
    candidate = run / "candidate"
    _write(candidate / "task.md", "# task\n\nFix the recovery decision.\n")
    _write(candidate / "gate" / "sim.py", "# frozen gate\n")
    _write(candidate / "tests" / "test_regression.py", "# frozen regression contract\n")
    _write(candidate / "skill" / "recovery.py", SOURCE)
    if telemetry:
        _write(candidate / "telemetry" / "execution.log", OWN_FEEDBACK)
    if stale:
        _write(candidate / "verdict.json", json.dumps(VERDICT) + "\n")
        _write(candidate / "telemetry" / "execution.log", OWN_FEEDBACK)
        _write(candidate / "experience" / "lesson.json", json.dumps({"lesson": "old"}) + "\n")
    verdict = run / "verdict"
    _write(verdict / "verdict.json", json.dumps(VERDICT, indent=2) + "\n")
    hidden = run / "hidden"
    _write(hidden / "answers.txt", "SEALED-ANSWER LEAK_MARKER\n")
    other = tmp_path / "run-a"
    _write(other / "telemetry" / "execution.log", OTHER_FEEDBACK)
    _write(other / "verdict.json", json.dumps({"passed": False}) + "\n")
    if link is not None:
        os.symlink(link, candidate / "alias.txt")
    return {"run": run, "candidate": candidate, "verdict": verdict,
            "hidden": hidden, "other": other}


def boundary(policy, tree, condition=vis.DEFAULT_CONDITION, **kwargs):
    return vis.RunBoundary(policy, tree["run"], tree["candidate"], tree["verdict"],
                           tree["hidden"], condition=condition, **kwargs)


# ---------------------------------------------------------------- policy table
def test_a_condition_sees_no_feedback_diagnosis_or_verdict(policy):
    assert policy.visible_categories("A_STATIC") == {"static_input", "candidate_source"}
    for category in ("execution_feedback", "diagnosis", "verification", "hidden_answer"):
        assert not policy.allows("A_STATIC", category)
    assert policy.guidance_for("A_STATIC") is None


def test_every_condition_keeps_the_verdict_and_hidden_answers_sealed(policy):
    for condition in vis.CONDITIONS:
        assert not policy.allows(condition, "verification"), condition
        assert not policy.allows(condition, "hidden_answer"), condition


def test_a_and_b_visible_sets_differ(policy):
    a_visible = set(policy.visible_categories("A_STATIC"))
    b_visible = set(policy.visible_categories("B_REAL_FEEDBACK"))
    assert a_visible < b_visible
    assert b_visible - a_visible == {"execution_feedback", "diagnosis"}
    matrix = vis.visibility_matrix(policy)
    # C and D share B's information *shape*; only the source and the guidance differ.
    assert matrix["C_MISMATCHED_FEEDBACK"] == matrix["B_REAL_FEEDBACK"]
    assert matrix["D_GUIDED"] == matrix["B_REAL_FEEDBACK"]


def test_the_same_tree_exposes_different_material_under_a_and_b(policy, tmp_path):
    tree = make_run(tmp_path, telemetry=True)
    a_tools = vis.ToolFacade(boundary(policy, tree, "A_STATIC"))
    b_tools = vis.ToolFacade(boundary(policy, tree, "B_REAL_FEEDBACK"))
    with pytest.raises(vis.AccessDenied):
        a_tools.read_telemetry()
    assert b_tools.read_telemetry() == OWN_FEEDBACK
    for tools in (a_tools, b_tools):
        with pytest.raises(vis.AccessDenied):
            tools.read_verification()


# ------------------------------------------------------------ loader refusals
def _mutate(doc, change):
    mutated = json.loads(json.dumps(doc))
    change(mutated)
    return mutated


def _a_reads_feedback(doc):
    doc["conditions"]["A_STATIC"]["visible"]["execution_feedback"] = True
    doc["conditions"]["A_STATIC"]["feedback_source"] = "own_run"


def _a_reads_diagnosis(doc):
    doc["conditions"]["A_STATIC"]["visible"]["diagnosis"] = True


def _a_feedback_source_without_visibility(doc):
    doc["conditions"]["A_STATIC"]["feedback_source"] = "own_run"


def _drop_condition(doc):
    del doc["conditions"]["D_GUIDED"]


def _add_condition(doc):
    doc["conditions"]["E_AUDITOR"] = doc["conditions"]["B_REAL_FEEDBACK"]


def _wrong_schema(doc):
    doc["schema_version"] = "repair-eval-visibility/0"


def _guidance_on_mismatched_feedback(doc):
    doc["conditions"]["C_MISMATCHED_FEEDBACK"]["guidance"] = "look at the retry branch"


def _guidance_on_two_conditions(doc):
    doc["conditions"]["B_REAL_FEEDBACK"]["guidance"] = "look at the retry branch"


def _guidance_too_long(doc):
    doc["conditions"]["D_GUIDED"]["guidance"] = "x" * (doc["guidance_max_chars"] + 1)


def _condition_exposes_hidden(doc):
    doc["conditions"]["B_REAL_FEEDBACK"]["visible"]["hidden_answer"] = True


def _freshness_drops_reserved_name(doc):
    doc["freshness"]["forbidden"] = [entry for entry in doc["freshness"]["forbidden"]
                                     if entry != "verdict.json"]


def _reserved_name_is_a_path(doc):
    doc["reserved_names"].append("sealed/verdict.json")


def _absolute_policy_path(doc):
    doc["paths"]["verdict"] = "/etc/passwd"


def _unknown_top_level_key(doc):
    doc["extra_knob"] = True


def _visible_misses_a_category(doc):
    del doc["conditions"]["A_STATIC"]["visible"]["hidden_answer"]


@pytest.mark.parametrize("change, expected", [
    (_a_reads_feedback, "A_STATIC must not expose"),
    (_a_reads_diagnosis, "A_STATIC must not expose"),
    (_a_feedback_source_without_visibility, "disagrees with execution_feedback"),
    (_drop_condition, "conditions must be exactly"),
    (_add_condition, "conditions must be exactly"),
    (_wrong_schema, "unsupported schema_version"),
    (_guidance_on_mismatched_feedback, "guidance may only extend"),
    (_guidance_on_two_conditions, "at most one condition may carry guidance"),
    (_guidance_too_long, "over guidance_max_chars"),
    (_condition_exposes_hidden, "hidden material is never agent visible"),
    (_freshness_drops_reserved_name, "must cover the reserved name"),
    (_reserved_name_is_a_path, "must be file names"),
    (_absolute_policy_path, "must be a relative path"),
    (_unknown_top_level_key, "unexpected="),
    (_visible_misses_a_category, "must declare exactly"),
])
def test_loader_refuses_a_policy_that_breaks_the_design(tmp_path, change, expected):
    doc = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    path = tmp_path / "mutated_policy.json"
    path.write_text(json.dumps(_mutate(doc, change)), encoding="utf-8")
    with pytest.raises(vis.PolicyError) as caught:
        vis.load_policy(path)
    assert expected in str(caught.value), str(caught.value)


def test_only_the_guided_condition_carries_guidance(policy):
    guided = [name for name in vis.CONDITIONS if policy.guidance_for(name) is not None]
    assert guided == ["D_GUIDED"], guided


def test_shipped_policy_loads_and_records_its_interface_versions(policy):
    assert policy.schema_version == vis.SCHEMA_VERSION
    assert policy.model_interface["tool_interface_version"] == "flexcell.repair_eval.tools/1"
    for key in ("model_id", "prompt_template_version"):
        assert key in policy.model_interface
    assert len(policy.fingerprint()) == 64


# ------------------------------------------------------- condition A refusals
def test_a_reads_static_input_and_candidate_source(policy, tmp_path):
    tree = make_run(tmp_path)
    tools = vis.ToolFacade(boundary(policy, tree, "A_STATIC"))
    assert "Fix the recovery decision" in tools.read_file("task.md")
    assert "def next_action" in tools.read_file("skill/recovery.py")
    assert "frozen regression contract" in tools.read_file("tests/test_regression.py")
    listing = tools.list_dir(".").splitlines()
    assert {"gate/", "skill/", "task.md", "tests/"} <= set(listing)
    hits = tools.search_code("next_action")
    assert "skill/recovery.py:4" in hits
    # reading does not rewrite the material
    assert (tree["candidate"] / "task.md").read_text(encoding="utf-8") == (
        "# task\n\nFix the recovery decision.\n")


def test_a_read_verdict_json_is_refused(policy, tmp_path):
    tree = make_run(tmp_path)
    gate = boundary(policy, tree, "A_STATIC")
    tools = vis.ToolFacade(gate)
    with pytest.raises(vis.AccessDenied) as caught:
        tools.read_file("verdict.json")
    assert caught.value.reason == vis.RESERVED_NAME
    assert caught.value.category == "candidate_source"
    denial = gate.denials()[-1]
    assert denial["path"] == "verdict.json"
    assert denial["decision"] == "deny"
    assert denial["reason"] == vis.RESERVED_NAME


def test_a_read_of_a_sibling_run_is_refused(policy, tmp_path):
    tree = make_run(tmp_path)
    tools = vis.ToolFacade(boundary(policy, tree, "A_STATIC"))
    with pytest.raises(vis.AccessDenied) as caught:
        tools.read_file("../run-a/verdict.json")
    assert caught.value.reason == vis.PARENT_TRAVERSAL
    with pytest.raises(vis.AccessDenied) as caught:
        tools.read_file("skill/../../run-a/verdict.json")
    assert caught.value.reason == vis.PARENT_TRAVERSAL


def test_a_read_of_an_absolute_path_is_refused(policy, tmp_path):
    tree = make_run(tmp_path)
    tools = vis.ToolFacade(boundary(policy, tree, "A_STATIC"))
    with pytest.raises(vis.AccessDenied) as caught:
        tools.read_file(str(tree["verdict"] / "verdict.json"))
    assert caught.value.reason == vis.ABSOLUTE_PATH


def test_a_read_through_a_symlink_alias_is_refused(policy, tmp_path):
    tree = make_run(tmp_path, link="../verdict/verdict.json")
    tools = vis.ToolFacade(boundary(policy, tree, "A_STATIC"))
    with pytest.raises(vis.AccessDenied) as caught:
        tools.read_file("alias.txt")
    assert caught.value.reason == vis.SYMLINK_ALIAS
    assert "verdict" in (caught.value.detail or "")


def test_a_symlink_to_hidden_material_is_refused(policy, tmp_path):
    tree = make_run(tmp_path, link="../hidden/answers.txt")
    tools = vis.ToolFacade(boundary(policy, tree, "A_STATIC"))
    with pytest.raises(vis.AccessDenied) as caught:
        tools.read_file("alias.txt")
    assert caught.value.reason == vis.SYMLINK_ALIAS


def test_a_cross_root_hard_link_is_refused(policy, tmp_path):
    tree = make_run(tmp_path)
    os.link(tree["verdict"] / "verdict.json", tree["candidate"] / "stolen.txt")
    tools = vis.ToolFacade(boundary(policy, tree, "A_STATIC"))
    with pytest.raises(vis.AccessDenied) as caught:
        tools.read_file("stolen.txt")
    assert caught.value.reason == vis.HARDLINK_ALIAS
    assert "verdict.json" in (caught.value.detail or "")


def test_a_telemetry_and_diagnosis_tools_are_refused(policy, tmp_path):
    tree = make_run(tmp_path, telemetry=True)
    tools = vis.ToolFacade(boundary(policy, tree, "A_STATIC"))
    for call in (tools.read_telemetry, tools.read_diagnosis, tools.read_verification):
        with pytest.raises(vis.AccessDenied) as caught:
            call()
        assert caught.value.reason == vis.POLICY_DENIED
    # the file tool cannot reach the feedback channel either
    with pytest.raises(vis.AccessDenied) as caught:
        tools.read_file("telemetry/execution.log")
    assert caught.value.category == "execution_feedback"


def test_attempts_record_every_decision_with_a_reason_code(policy, tmp_path):
    tree = make_run(tmp_path)
    gate = boundary(policy, tree, "A_STATIC")
    tools = vis.ToolFacade(gate)
    tools.read_file("skill/recovery.py")
    with pytest.raises(vis.AccessDenied):
        tools.read_file("verdict.json")
    decisions = [entry["decision"] for entry in gate.attempts]
    assert "allow" in decisions and "deny" in decisions
    denied = gate.denials()
    assert denied
    assert all(entry["reason"] in vis.REASON_CODES for entry in denied)
    assert gate.denial_reasons() == [vis.RESERVED_NAME]
    assert all(entry["condition"] == "A_STATIC" for entry in gate.attempts)


# ------------------------------------------------------------- feedback packets
def test_no_feedback_is_none_not_an_empty_string(policy, tmp_path):
    tree = make_run(tmp_path, telemetry=True)
    assert vis.collect_feedback(boundary(policy, tree, "A_STATIC"), run_id="run-b") is None


def test_b_feedback_packet_carries_its_own_source_and_digest(policy, tmp_path):
    tree = make_run(tmp_path, telemetry=True)
    packet = vis.collect_feedback(boundary(policy, tree, "B_REAL_FEEDBACK"), run_id="run-b")
    assert packet is not None
    assert packet.condition == "B_REAL_FEEDBACK"
    assert packet.mismatched is False
    assert packet.source_run_id == "run-b"
    assert packet.source_root == "candidate"
    assert packet.text == OWN_FEEDBACK
    assert packet.sha256 == hashlib.sha256(OWN_FEEDBACK.encode("utf-8")).hexdigest()
    assert packet.guidance is None


def test_c_feedback_is_the_fixed_other_run_and_is_tagged(policy, tmp_path):
    tree = make_run(tmp_path, telemetry=True)
    packet = vis.collect_feedback(
        boundary(policy, tree, "C_MISMATCHED_FEEDBACK", mismatch_dir=tree["other"]),
        run_id="run-b", mismatch_run_id="run-a")
    assert packet is not None
    assert packet.mismatched is True
    assert packet.source_run_id == "run-a"
    assert packet.source_root == "mismatch"
    assert packet.text == OTHER_FEEDBACK
    assert packet.sha256 == hashlib.sha256(OTHER_FEEDBACK.encode("utf-8")).hexdigest()
    own = vis.collect_feedback(boundary(policy, tree, "B_REAL_FEEDBACK"), run_id="run-b")
    assert packet.sha256 != own.sha256
    assert packet.mismatched and not own.mismatched


def test_c_without_a_mismatch_run_fails_closed(policy, tmp_path):
    tree = make_run(tmp_path, telemetry=True)
    with pytest.raises(vis.PolicyError):
        vis.collect_feedback(boundary(policy, tree, "C_MISMATCHED_FEEDBACK"),
                             run_id="run-b", mismatch_run_id="run-a")
    with pytest.raises(vis.BoundaryError):
        vis.collect_feedback(
            boundary(policy, tree, "C_MISMATCHED_FEEDBACK", mismatch_dir=tree["other"]),
            run_id="run-b")


def test_d_adds_bounded_guidance_on_top_of_real_feedback(policy, tmp_path):
    tree = make_run(tmp_path, telemetry=True)
    packet = vis.collect_feedback(boundary(policy, tree, "D_GUIDED"), run_id="run-b")
    guidance = policy.guidance_for("D_GUIDED")
    assert guidance and packet.guidance == guidance
    assert 0 < len(packet.guidance) <= policy.guidance_max_chars
    assert packet.guidance_sha256 == hashlib.sha256(guidance.encode("utf-8")).hexdigest()
    assert packet.text == OWN_FEEDBACK
    assert packet.mismatched is False
    # the guidance comes from the policy document; nothing sealed leaks with it
    assert "LEAK_MARKER" not in json.dumps(packet.as_dict())
    assert guidance in POLICY_PATH.read_text(encoding="utf-8")


def test_diagnosis_is_a_bounded_projection_of_the_run_own_feedback(policy, tmp_path):
    tree = make_run(tmp_path, telemetry=True)
    diagnosis = vis.ToolFacade(boundary(policy, tree, "B_REAL_FEEDBACK")).read_diagnosis()
    assert diagnosis is not None
    assert diagnosis["parses_json"] is True
    assert diagnosis["root"] == "candidate"
    assert set(diagnosis["doc"]) <= set(policy.diagnosis["projection"])
    assert "secret" not in diagnosis["doc"]
    assert diagnosis["doc"]["stdout"].startswith("run-b")
    assert "LEAK_MARKER" not in json.dumps(diagnosis)


# ------------------------------------------------------------------- freshness
def test_stale_candidate_is_refused(policy, tmp_path):
    tree = make_run(tmp_path, stale=True)
    stale_policy = replace(policy, freshness_max_depth=policy.freshness_max_depth)
    gate = vis.RunBoundary(stale_policy, tree["run"], tree["candidate"],
                           tree["verdict"], tree["hidden"], condition="B_REAL_FEEDBACK")
    with pytest.raises(vis.StaleArtifact) as caught:
        gate.assert_fresh_run()
    artifacts = caught.value.artifacts
    paths = [item["path"] for item in artifacts]
    assert "verdict.json" in paths
    assert "telemetry" in paths
    assert "experience" in paths
    assert all(item["kind"] in ("file", "dir", "symlink") for item in artifacts)
    assert caught.value.as_dict()["reason"] == vis.STALE_ARTIFACT


def test_module_level_freshness_check_matches_the_boundary(policy, tmp_path):
    tree = make_run(tmp_path, stale=True)
    with pytest.raises(vis.StaleArtifact):
        vis.assert_fresh_run(policy, tree["candidate"])


def test_fresh_candidate_passes(policy, tmp_path):
    tree = make_run(tmp_path)
    assert boundary(policy, tree, "A_STATIC").assert_fresh_run() is True


def test_freshness_does_not_count_frozen_static_input(policy, tmp_path):
    tree = make_run(tmp_path)
    artifacts = vis.scan_freshness(policy, tree["candidate"])
    assert artifacts == []


# --------------------------------------------------------------- write gating
def test_protected_writes_are_refused(policy, tmp_path):
    tree = make_run(tmp_path)
    tools = vis.ToolFacade(boundary(policy, tree, "A_STATIC"))
    for rel in ("gate/sim.py", "tests/test_regression.py", "task.md", "verdict.json"):
        with pytest.raises(vis.AccessDenied) as caught:
            tools.write_file(rel, "tampered\n")
        assert caught.value.reason == vis.PROTECTED_WRITE
    assert (tree["candidate"] / "gate" / "sim.py").read_text(encoding="utf-8") == "# frozen gate\n"


def test_candidate_source_write_is_allowed(policy, tmp_path):
    tree = make_run(tmp_path)
    tools = vis.ToolFacade(boundary(policy, tree, "A_STATIC"))
    assert tools.write_file("skill/recovery.py", SOURCE.replace("ABORT", "OBSERVE"))
    assert "OBSERVE" in (tree["candidate"] / "skill" / "recovery.py").read_text(encoding="utf-8")


def test_write_outside_the_candidate_is_refused(policy, tmp_path):
    tree = make_run(tmp_path)
    tools = vis.ToolFacade(boundary(policy, tree, "A_STATIC"))
    for rel, expected in (
        ("../verdict/verdict.json", vis.PARENT_TRAVERSAL),
        (str(tree["hidden"] / "answers.txt"), vis.ABSOLUTE_PATH),
    ):
        with pytest.raises(vis.AccessDenied) as caught:
            tools.write_file(rel, "tampered\n")
        assert caught.value.reason == expected
    assert (tree["verdict"] / "verdict.json").is_file()
    assert (tree["hidden"] / "answers.txt").read_text(encoding="utf-8") == "SEALED-ANSWER LEAK_MARKER\n"


# --------------------------------------------------------------- search gating
def test_search_does_not_reach_the_verdict_or_hidden_material(policy, tmp_path):
    tree = make_run(tmp_path)
    tools = vis.ToolFacade(boundary(policy, tree, "A_STATIC"))
    assert tools.search_code("LEAK_MARKER") == "(no matches)"
    assert tools.search_code("SEALED") == "(no matches)"
    assert "skill/recovery.py:4" in tools.search_code("next_action")


# ------------------------------------------------------- policy-driven, not fixed
def test_verification_access_is_policy_driven(policy, tmp_path):
    tree = make_run(tmp_path)
    with pytest.raises(vis.AccessDenied) as caught:
        boundary(policy, tree, "A_STATIC").read_verification()
    assert caught.value.reason == vis.POLICY_DENIED
    # widen only the loaded policy object: the gate follows the policy, it is not
    # a hardcoded refusal.  (No shipped condition does this; the test proves the
    # mechanism, not a protocol decision.)
    access = policy.conditions["D_GUIDED"]
    widened = replace(policy, conditions={
        **policy.conditions,
        "D_GUIDED": replace(access, visible={**access.visible, "verification": True}),
    })
    text = boundary(widened, tree, "D_GUIDED").read_verification()
    assert json.loads(text)["answer"] == "LEAK_MARKER"


# ------------------------------------------------------------- configuration
def test_overlapping_roots_are_rejected(policy, tmp_path):
    tree = make_run(tmp_path)
    with pytest.raises(vis.PolicyError) as caught:
        vis.RunBoundary(policy, tree["run"], tree["candidate"], tree["candidate"], tree["hidden"])
    assert "roots overlap" in str(caught.value)
    inside = tree["candidate"] / "hidden-inside"
    inside.mkdir()
    with pytest.raises(vis.PolicyError) as caught:
        vis.RunBoundary(policy, tree["run"], tree["candidate"], tree["verdict"], inside)
    assert "roots overlap" in str(caught.value)


def test_default_condition_is_the_most_restrictive(policy, tmp_path):
    tree = make_run(tmp_path, telemetry=True)
    default = vis.RunBoundary(policy, tree["run"], tree["candidate"],
                              tree["verdict"], tree["hidden"])
    assert default.condition == "A_STATIC"
    with pytest.raises(vis.AccessDenied):
        default.read_feedback()


def test_describe_records_the_policy_binding(policy, tmp_path):
    tree = make_run(tmp_path, telemetry=True)
    described = boundary(policy, tree, "B_REAL_FEEDBACK").describe()
    assert described["condition"] == "B_REAL_FEEDBACK"
    assert described["policy_fingerprint"] == policy.fingerprint()
    assert described["schema_version"] == vis.SCHEMA_VERSION
    assert described["visible_categories"] == sorted(policy.visible_categories("B_REAL_FEEDBACK"))
    assert described["feedback_source"] == "own_run"
    assert described["roots"]["mismatch"] is None


# --------------------------------------------------------------------- demo CLI
def test_demo_command_prints_the_three_required_examples():
    proc = subprocess.run(
        [sys.executable, "-m", "benchmark.repair_eval.visibility", "--demo"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    examples = payload["examples"]
    assert examples["allowed_read"]["sha256"]
    assert examples["allowed_read"]["path"] == "skill/recovery.py"
    assert examples["refused_reserved_name"]["reason"] == vis.RESERVED_NAME
    assert examples["refused_parent_traversal"]["reason"] == vis.PARENT_TRAVERSAL
    assert examples["refused_feedback_tool"]["reason"] == vis.POLICY_DENIED
    assert examples["no_feedback"]["is_none"] is True
    assert examples["refused_stale_inheritance"]["refused"] is True
    assert examples["mismatched_feedback"]["packet"]["mismatched"] is True
    assert examples["guided_feedback"]["within_policy_bound"] is True
