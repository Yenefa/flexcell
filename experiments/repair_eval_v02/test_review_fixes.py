"""Regressions for the #249–#254 review, including the actual agent adapter."""
from argparse import Namespace
import copy
import json
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from benchmark.repair_eval import visibility as V
from benchmark.repair_eval.contracts import acceptance, casefile, task_contract
from agent import RepairAgent
import budget
import dispatch_plan as DP
import health
import run_matrix_real as R
import reconcile as RC


def boundary(tmp_path, condition):
    for name in ("candidate", "verdict", "hidden", "donor"):
        (tmp_path / name).mkdir()
    candidate, donor = tmp_path / "candidate", tmp_path / "donor"
    for root, text in ((candidate, "OWN_FEEDBACK_MARKER"), (donor, "DONOR_FEEDBACK_MARKER")):
        (root / "telemetry").mkdir()
        (root / "telemetry/execution.log").write_text(text)
    (candidate / "gate").mkdir()
    (candidate / "gate/check.py").write_text("SEALED_GATE_MARKER")
    (candidate / "task.md").write_text("immutable task")
    (candidate / "source.py").write_text("editable source")
    return V.RunBoundary(V.load_policy(), tmp_path, candidate, tmp_path / "verdict",
                         tmp_path / "hidden", condition=condition, mismatch_dir=donor)


@pytest.mark.parametrize("condition", ("A_STATIC", "B_REAL_FEEDBACK", "C_MISMATCHED_FEEDBACK"))
@pytest.mark.parametrize("operation", ("read_file", "search", "edit_file"))
def test_actual_agent_preserves_feedback_condition(tmp_path, condition, operation):
    bound = boundary(tmp_path, condition)
    target = ["telemetry/execution.log", 1, 20] if operation == "read_file" else \
        ["telemetry/execution.log", "FEEDBACK_MARKER"] if operation == "search" else \
        ["telemetry/execution.log", "NOT_FOUND_ANCHOR", "replacement"]

    class Transport:
        def __init__(self):
            self.requests = []

        def chat(self, messages, **kw):
            self.requests.append(messages)
            actions = [{operation: target}] if len(self.requests) == 1 else []
            return {"text": json.dumps({"actions": actions, "done": not actions}),
                    "usage": {"total_tokens": 0}}

    transport = Transport()
    agent = RepairAgent(budget.Ledger(transport), bound, "repair source", ["source.py"])
    agent.run()
    sent = json.dumps(transport.requests[-1])
    assert ("OWN_FEEDBACK_MARKER" in sent) == (condition == "B_REAL_FEEDBACK")
    assert ("DONOR_FEEDBACK_MARKER" in sent) == (condition == "C_MISMATCHED_FEEDBACK")


@pytest.mark.parametrize("condition", V.CONDITIONS)
@pytest.mark.parametrize("kind", ("symlink", "hardlink"))
def test_internal_alias_cannot_read_or_overwrite_gate(tmp_path, condition, kind):
    bound = boundary(tmp_path, condition)
    alias = bound.candidate / "alias.py"
    target = bound.candidate / "gate/check.py"
    alias.symlink_to(target) if kind == "symlink" else alias.hardlink_to(target)
    tools = V.ToolFacade(bound)
    for action in (lambda: tools.read_file("alias.py"),
                   lambda: tools.write_file("alias.py", "fake gate")):
        with pytest.raises(V.AccessDenied):
            action()
    assert target.read_text() == "SEALED_GATE_MARKER"


@pytest.mark.parametrize("kind", ("symlink", "hardlink"))
def test_a_cannot_read_feedback_via_internal_alias(tmp_path, kind):
    bound = boundary(tmp_path, "A_STATIC")
    target = bound.candidate / "telemetry/execution.log"
    alias = bound.candidate / "source_alias.txt"
    alias.symlink_to(target) if kind == "symlink" else alias.hardlink_to(target)
    with pytest.raises(V.AccessDenied):
        V.ToolFacade(bound).read_file("source_alias.txt")
    with pytest.raises(V.AccessDenied):
        bound.read_text("telemetry/execution.log", "candidate_source")


def test_alias_to_static_task_remains_readable_but_is_not_writable(tmp_path):
    bound = boundary(tmp_path, "A_STATIC")
    (bound.candidate / "alias.txt").symlink_to("task.md")
    tools = V.ToolFacade(bound)
    assert tools.read_file("alias.txt") == "immutable task"
    with pytest.raises(V.AccessDenied):
        tools.write_file("alias.txt", "changed goal")


def test_c_search_reads_donor_root_without_candidate_feedback(tmp_path):
    bound = boundary(tmp_path, "C_MISMATCHED_FEEDBACK")
    (bound.candidate / "telemetry/notes.txt").write_text("OWN_FEEDBACK_MARKER")
    (bound.mismatch / "telemetry/notes.txt").write_text("DONOR_FEEDBACK_MARKER")
    result = V.ToolFacade(bound).search_code("FEEDBACK_MARKER", path="telemetry")
    assert "DONOR_FEEDBACK_MARKER" in result and "OWN_FEEDBACK_MARKER" not in result


@pytest.mark.parametrize("names", (("detach_baseline", "detach_baseline"),
                                   (None, None), ("", " "),
                                   ("detach_baseline", " detach_baseline ")))
def test_duplicate_and_missing_regression_identities_cannot_replace_two_checks(names):
    case = casefile.load(REG_CASE)
    state = copy.deepcopy(case["candidate"])
    state["regressions"] = [{"name": name, "status": "PASS"} for name in names]
    verdict = acceptance.evaluate(task_contract.TaskContract.from_mapping(case["contract"]), state)
    assert verdict.status != "ACCEPT"
    assert "REGRESSION_MISSING" in verdict.codes


REG_CASE = ROOT / "benchmark/repair_eval/contracts/cases/p1_valid_repair.json"


def test_selection_keeps_registered_order_even_when_filters_are_reversed():
    plan = DP.load()
    selected = DP.select(plan, list(reversed(R.FAMILIES)), list(reversed(R.CONDITIONS)), [3, 2, 1])
    # The registered order now runs every A/B repetition before any C, because a
    # C slot's registered donor has to exist when it is dispatched. Measured on
    # the first real dispatch: in the previous order both C slots came back
    # NOT_RUN and the batch stopped.
    assert [r["slot_id"] for r in selected[:6]] == [
        "F1-A-r1", "F2-A-r1", "F1-A-r2", "F2-A-r2", "F1-A-r3", "F2-A-r3"]
    assert selected == plan["slots"]
    with pytest.raises(ValueError, match="not registered"):
        DP.select(plan, [R.FAMILIES[0]], ["A_STATIC"], [4])


def test_dispatch_uses_exact_registered_donor_and_keeps_missing_donor_not_run(tmp_path, monkeypatch):
    calls = []

    def run(family, condition, rep, work, *args, **kwargs):
        slot = "F1-%s-r%d" % (condition[0], rep)
        calls.append((slot, kwargs["donor_run_id"], kwargs["seed"]))
        (work / "candidate").mkdir()
        (work / "candidate/source.py").write_text("source")
        donor = work / "donor_output" / (slot + ".log")
        donor.parent.mkdir()
        donor.write_text(slot)
        return {"terminal_status": "FAIL", "action_terminal": health.TYPED_FAILURE,
                "donor_log": str(donor), "tokens_total": 0, "qualification": "SCRIPTED_TEST"}

    monkeypatch.setattr(R, "run_slot", run)
    args = Namespace(out=str(tmp_path / "batch.json"), model="SCRIPTED_TEST", limit=0,
                     budget=100, max_interactions=6, source="instances", task_variant="v2")
    sha = health.checked_run(["git", "rev-parse", "HEAD"], cwd=ROOT).stdout.strip()
    report = R.execute_batch(args, None, [R.FAMILIES[0]], ["B_REAL_FEEDBACK", "C_MISMATCHED_FEEDBACK"],
                             [1, 2], sha, {})
    # With the reordered plan both B repetitions run before the C slots, so the
    # donor a C slot names already exists when it is dispatched.
    assert [r["slot_id"] for r in report["rows"]] == [
        "F1-B-r1", "F1-B-r2", "F1-C-r1", "F1-C-r2"]
    assert report["rows"][2]["terminal_status"] == "FAIL"
    assert calls[0] == ("F1-B-r1", None, 5101)
    assert calls[1] == ("F1-B-r2", None, 5102)
    assert [c[0] for c in calls[2:]] == ["F1-C-r1", "F1-C-r2"]
    assert all(c[1] for c in calls[2:]), "a C slot ran without a donor"
    assert report["summary"]["plan_sha256"] == DP.load()["sha256"]


def test_status_agreement_does_not_hide_order_deviation():
    report = RC.reconcile({"a": "FAIL", "b": "FAIL"}, [
        {"slot_id": "b", "terminal_status": "FAIL"},
        {"slot_id": "a", "terminal_status": "FAIL"}])
    assert report["consistent"] and not report["order_matches"]


def test_a_c_slot_without_its_donor_stays_not_run(tmp_path, monkeypatch):
    """The donor rule survives the reorder: selecting C alone cannot invent one."""
    calls = []

    def run(family, condition, rep, work, *args, **kwargs):
        calls.append(kwargs["donor_run_id"])
        (work / "candidate").mkdir()
        (work / "candidate/source.py").write_text("source")
        return {"terminal_status": "FAIL", "action_terminal": health.TYPED_FAILURE,
                "tokens_total": 0, "qualification": "SCRIPTED_TEST"}

    monkeypatch.setattr(R, "run_slot", run)
    args = Namespace(out=str(tmp_path / "batch.json"), model="SCRIPTED_TEST", limit=0,
                     budget=100, max_interactions=6, source="instances", task_variant="v2")
    sha = health.checked_run(["git", "rev-parse", "HEAD"], cwd=ROOT).stdout.strip()
    report = R.execute_batch(args, None, [R.FAMILIES[0]], ["C_MISMATCHED_FEEDBACK"],
                             [1, 2], sha, {})
    assert [r["terminal_status"] for r in report["rows"]] == ["NOT_RUN", "NOT_RUN"]
    assert calls == []
