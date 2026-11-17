"""Injected faults must suppress dispatch and preserve the only workspace."""
from argparse import Namespace
import json
from pathlib import Path
import subprocess
import sys
from urllib.error import URLError

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evidence_archive as ARCH
import health
import run_matrix_real as R


def sha():
    return health.checked_run(["git", "rev-parse", "HEAD"], cwd=R.ROOT).stdout.strip()


def args(tmp_path):
    return Namespace(out=str(tmp_path / "batch.json"), budget=100, limit=0,
                     model="TEST_DOUBLE", max_interactions=6, source="instances",
                     task_variant="v2")


def fake_slot(calls, fault=None, terminal="UNKNOWN"):
    def run(family, condition, rep, workdir, *pos, **kw):
        calls.append(rep)
        candidate = workdir / "candidate"
        candidate.mkdir()
        (candidate / "repair.py").write_text("repair survives cleanup\n")
        ARCH.write_json(workdir / "account.json", {"tokens_total": 7, "interactions_used": 1})
        if fault:
            raise fault
        return {"terminal_status": terminal, "action_terminal": health.SUCCESS,
                "tokens_total": 7, "interactions_used": 1, "qualification": "TEST_DOUBLE"}
    return run


def batch(tmp_path):
    return R.execute_batch(args(tmp_path), None, [R.FAMILIES[0]], ["A_STATIC"],
                           [1, 2, 3], sha(), {})


@pytest.mark.parametrize("phase", (1, 2))
def test_unhealthy_before_or_after_slot_stops_all_further_dispatch(tmp_path, monkeypatch, phase):
    calls, probes = [], []
    original = health.probe

    def injected(*pos, **kw):
        result = original(*pos, **kw)
        probes.append(result)
        if len(probes) == phase:
            result.update(healthy=False, failures=["INJECTED_UNHEALTHY"])
        return result

    monkeypatch.setattr(health, "probe", injected)
    monkeypatch.setattr(R, "run_slot", fake_slot(calls))
    report = batch(tmp_path)
    assert calls == ([] if phase == 1 else [1])
    assert [r["terminal_status"] for r in report["rows"]] == ["INVALID", "NOT_RUN", "NOT_RUN"]
    archived = Path(report["rows"][0]["archive"]["path"])
    ARCH.verify(archived)
    assert (archived / "exception.json").exists()
    assert not (archived.parents[1] / "working" / "F1-A-r1").exists()
    if phase == 2:
        assert (archived / "candidate" / "repair.py").read_text() == "repair survives cleanup\n"


@pytest.mark.parametrize("fault,state", [
    (health.UnconfirmedAction(health.TIMEOUT, "injected"), health.TIMEOUT),
    (health.UnconfirmedAction(health.NO_RESPONSE, "injected"), health.NO_RESPONSE),
    (subprocess.TimeoutExpired("candidate", 1), health.TIMEOUT),
    (ConnectionError("model disconnected"), health.NO_RESPONSE),
    (URLError(TimeoutError("model timed out")), health.TIMEOUT),
])
def test_unknown_terminal_stops_and_keeps_cost_and_workspace(tmp_path, monkeypatch, fault, state):
    calls = []
    monkeypatch.setattr(R, "run_slot", fake_slot(calls, fault))
    report = batch(tmp_path)
    assert calls == [1]
    row = report["rows"][0]
    assert row["terminal_status"] == "UNKNOWN" and row["action_terminal"] == state
    assert report["summary"]["tokens_spent"] == 7
    assert [r["terminal_status"] for r in report["rows"][1:]] == ["NOT_RUN", "NOT_RUN"]
    assert (Path(row["archive"]["path"]) / "candidate" / "repair.py").is_file()
    ARCH.verify(row["archive"]["path"])


def test_missing_independent_verdict_does_not_mean_action_hung(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(R, "run_slot", fake_slot(calls))
    report = batch(tmp_path)
    assert calls == [1, 2, 3]
    assert report["summary"]["stopped"] is None
    assert all(row["terminal_status"] == "UNKNOWN" for row in report["rows"])


def test_typed_task_failure_keeps_dispatching(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(R, "run_slot", fake_slot(calls, terminal="FAIL"))
    report = batch(tmp_path)
    assert calls == [1, 2, 3]
    assert all(row["terminal_status"] == "FAIL" for row in report["rows"])


def test_failed_archive_keeps_original_and_stops_dispatch(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(R, "run_slot", fake_slot(calls))

    def broken(*pos, **kw):
        raise OSError("injected disk failure")

    monkeypatch.setattr(ARCH, "preserve", broken)
    report = batch(tmp_path)
    assert calls == [1]
    assert report["summary"]["stopped"] == "ARCHIVE_FAILED"
    assert (Path(report["rows"][0]["preserved_workdir"]) / "candidate" / "repair.py").exists()
    assert json.loads(Path(args(tmp_path).out).read_text())["summary"]["running"] is False


def test_source_dependency_and_workspace_mutations_fail_probe(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    protected = candidate / "task.md"
    protected.write_text("immutable")
    baseline = health.inventory(candidate)
    assert health.probe(R.ROOT, sha(), candidate, baseline=baseline)["healthy"]
    for changes in ({"expected_sha": "0" * 40},
                    {"dependencies": ("nonexistent_evobot_dependency_252",)},
                    {"required_files": ("gate/check.py",)}):
        kwargs = dict(source_root=R.ROOT, expected_sha=sha(), workspace=candidate)
        kwargs.update(changes)
        assert not health.probe(**kwargs)["healthy"]
    protected.write_text("tampered")
    assert not health.probe(R.ROOT, sha(), candidate, baseline=baseline)["healthy"]
    assert not health.probe(R.ROOT, sha(), candidate, backend="gazebo")["healthy"]


@pytest.mark.parametrize("code,expected", [(0, health.SUCCESS), (1, health.TYPED_FAILURE)])
def test_confirmed_process_results(code, expected):
    assert health.pytest_terminal(subprocess.CompletedProcess("pytest", code)) == expected


@pytest.mark.parametrize("code", (-9, 2, 3, 4, 5))
def test_no_test_or_interrupted_process_is_unconfirmed(code):
    with pytest.raises(health.UnconfirmedAction):
        health.pytest_terminal(subprocess.CompletedProcess("pytest", code))


def test_three_exhausted_slots_stop_according_to_protocol(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(R, "run_slot", fake_slot(calls, terminal="BUDGET_EXHAUSTED"))
    config = args(tmp_path)
    plan = tmp_path / "test-plan.json"
    ARCH.write_json(plan, {"schema": "evobot.dispatch_plan/1", "plan_id": "TEST_FOUR_SLOTS",
                          "slots": [{"slot_id": "F1-A-r%d" % r, "seed": 5100 + r}
                                    for r in range(1, 5)]})
    config.plan = str(plan)
    report = R.execute_batch(config, None, [R.FAMILIES[0]], ["A_STATIC"],
                             [1, 2, 3, 4], sha(), {})
    assert calls == [1, 2, 3]
    assert report["rows"][3]["terminal_status"] == "NOT_RUN"
    assert report["summary"]["stopped"] == "THREE_CONSECUTIVE_BUDGET_EXHAUSTED"


def test_actual_slot_empty_model_reply_is_unconfirmed_and_accounted(tmp_path, monkeypatch):
    class BlankTransport:
        def chat(self, *pos, **kw):
            return {"text": "", "usage": {"total_tokens": 11}}

    monkeypatch.setattr(R, "GatedTransport", lambda **kw: BlankTransport())
    policy = R.vis.load_policy(R.ROOT / "benchmark/repair_eval/visibility_policy.json")
    report = R.execute_batch(args(tmp_path), policy, [R.FAMILIES[0]], ["A_STATIC"],
                             [1, 2], sha(), {})
    assert report["rows"][0]["action_terminal"] == "NO_RESPONSE"
    assert report["rows"][1]["terminal_status"] == "NOT_RUN"
    assert report["summary"]["tokens_spent"] == 11
    ARCH.verify(report["rows"][0]["archive"]["path"])


def test_probe_exception_is_an_unhealthy_stop_with_remaining_slots_not_run(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(R, "run_slot", fake_slot(calls))

    def broken(*pos, **kw):
        raise OSError("injected probe failure")

    monkeypatch.setattr(health, "probe", broken)
    report = batch(tmp_path)
    assert not calls
    assert report["rows"][0]["terminal_status"] == "INVALID"
    assert report["rows"][1]["terminal_status"] == "NOT_RUN"
    assert Path(report["rows"][0]["archive"]["path"]).is_dir()


@pytest.mark.parametrize("condition", ("B_REAL_FEEDBACK", "D_GUIDED"))
def test_guidance_record_matches_what_the_model_actually_received(tmp_path, monkeypatch, condition):
    class CapturingTransport:
        def __init__(self):
            self.seen = []

        def chat(self, messages, **kw):
            self.seen.extend(messages)
            return {"text": '{"actions":[],"done":true}', "usage": {"total_tokens": 1}}

        def metadata(self):
            return {"requested_model": "TEST_DOUBLE", "key_fingerprint": "NONE"}

    transport = CapturingTransport()
    monkeypatch.setattr(R, "GatedTransport", lambda **kw: transport)
    policy = R.vis.load_policy(R.ROOT / "benchmark/repair_eval/visibility_policy.json")
    donor = tmp_path / "donor"
    donor.mkdir()
    work = tmp_path / "slot"
    work.mkdir()
    row = R.run_slot(R.FAMILIES[0], condition, 1, work, policy, donor,
                     "TEST_DOUBLE", 6, source_sha=sha(), source="instances", task_variant="v2")
    sent = [m["content"] for m in transport.seen if m["content"].startswith("GUIDANCE\n")]
    if condition == "D_GUIDED":
        assert sent == ["GUIDANCE\n" + policy.conditions[condition].guidance]
        assert row["guidance_sha256"]
    else:
        assert not sent and row["guidance_sha256"] is None
