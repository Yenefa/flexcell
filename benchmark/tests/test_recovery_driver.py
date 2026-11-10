#!/usr/bin/env python3
"""Recovery driver tests: triggered by EXECUTION evidence, never by the verdict."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime" / "recovery"))
import recovery_driver as rd


def _w(p, text):
    p.write_text(text, encoding="utf-8")


def _result(**kw):
    return "RESULT " + json.dumps(kw)


def test_successful_first_attempt_does_not_trigger_recovery(tmp_path):
    _w(tmp_path / "task.out", _result(outcome=0, error_code=0, detail="ok",
                                      completed_stage_ids=["a-0"]))
    rd.main(["--run", str(tmp_path)])
    d = json.loads((tmp_path / "recovery_decision.json").read_text())
    assert d["action"] == "no_recovery"
    assert not (tmp_path / "plan_retry.json").exists()


def test_uncommitted_planning_failure_gets_a_bounded_action(tmp_path):
    _w(tmp_path / "task.out", _result(outcome=1, error_code=61,
                                      detail="state drift or occupied destination before b-1",
                                      completed_stage_ids=[]))
    _w(tmp_path / "plan.json", json.dumps({
        "stages": [{"object_name": "a", "place_pose": [0.12, -0.15, 0.0175]},
                   {"object_name": "b", "place_pose": [0.12, -0.15, 0.0175]}],
        "clearance_m": 0.05, "position_tolerance_m": 0.02}))
    assert rd.main(["--run", str(tmp_path)]) == 0
    rec = json.loads((tmp_path / "recovery_decision.json").read_text())
    assert rec["decision"]["failure_class"] == "planning"
    assert rec["decision"]["action"] == "respread"
    assert rec["original_failure_preserved"] is True
    retry = json.loads((tmp_path / "plan_retry.json").read_text())
    p0, p1 = retry["stages"][0]["place_pose"], retry["stages"][1]["place_pose"]
    assert p0 != p1
    assert abs(p0[0] - p1[0]) >= 0.09 - 1e-9, abs(p0[0] - p1[0])
    assert retry["clearance_m"] == 0.05 and retry["position_tolerance_m"] == 0.02


def test_partial_commit_refuses_replay_and_asks_for_resume(tmp_path):
    _w(tmp_path / "task.out", _result(outcome=1, error_code=61,
                                      detail="state drift or occupied destination before b-1",
                                      completed_stage_ids=["a-0"]))
    _w(tmp_path / "plan.json", json.dumps({"stages": [
        {"object_name": "a", "place_pose": [0.12, -0.15, 0.0175]}]}))
    assert rd.main(["--run", str(tmp_path)]) == 1
    rec = json.loads((tmp_path / "recovery_decision.json").read_text())
    assert rec["decision"]["action"] == "resume_required"
    assert rec["decision"]["committed_stages"] == ["a-0"]
    assert not (tmp_path / "plan_retry.json").exists()


def test_partial_commit_resumes_from_measured_state(tmp_path):
    _w(tmp_path / "task.out", _result(outcome=1, error_code=61,
                                      detail="state drift or occupied destination before b-1",
                                      completed_stage_ids=["a-0"]))
    _w(tmp_path / "plan.json", json.dumps({
        "initial_objects": [{"object_name": "a", "position": [0.22, 0.0, 0.0175]},
                            {"object_name": "b", "position": [0.20, -0.18, 0.0175]}],
        "stages": [{"stage_id": "a-0", "object_name": "a",
                    "place_pose": [0.092, -0.15, 0.0175]},
                   {"stage_id": "b-1", "object_name": "b",
                    "place_pose": [0.148, -0.15, 0.0175]}],
        "clearance_m": 0.05, "position_tolerance_m": 0.02}))
    gt = tmp_path / "gt.json"
    _w(gt, json.dumps({"objects": {"a": [0.100, -0.156, 0.0175, 0.0],
                                   "b": [0.200, -0.180, 0.0175, 0.0]}}))
    assert rd.main(["--run", str(tmp_path), "--ground-truth", str(gt)]) == 0
    retry = json.loads((tmp_path / "plan_retry.json").read_text())
    assert [s["stage_id"] for s in retry["stages"]] == ["b-1"]
    assert retry["resumed_from_stage_ids"] == ["a-0"]
    assert retry["initial_objects"][0]["position"] == [0.100, -0.156, 0.0175]
    assert retry["clearance_m"] == 0.05 and retry["position_tolerance_m"] == 0.02
    rec = json.loads((tmp_path / "recovery_decision.json").read_text())
    assert rec["decision"]["action"] == "resume"


def test_resume_refuses_when_measured_state_is_missing(tmp_path):
    _w(tmp_path / "task.out", _result(outcome=1, error_code=61, detail="occupied",
                                      completed_stage_ids=["a-0"]))
    _w(tmp_path / "plan.json", json.dumps({
        "initial_objects": [{"object_name": "a", "position": [0.22, 0.0, 0.0175]}],
        "stages": [{"stage_id": "b-1", "object_name": "b",
                    "place_pose": [0.148, -0.15, 0.0175]}]}))
    gt = tmp_path / "gt.json"
    _w(gt, json.dumps({"objects": {}}))
    assert rd.main(["--run", str(tmp_path), "--ground-truth", str(gt)]) == 1
    assert not (tmp_path / "plan_retry.json").exists()


def _place_failure_journal(tmp_path):
    d = tmp_path / "sim" / "skills" / "composites"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "composite-test.jsonl"
    p.write_text(json.dumps({"event": "NATIVE_TERMINAL", "stage_id": "a-0",
                             "component": {"outcome": 1, "error_code": 50,
                                           "detail": "place failed",
                                           "final_state": {"fsm_trace":
                                               ["PICK_A:OK", "PLACE_A:FAIL"]}}}) + "\n",
                 encoding="utf-8")


def test_failed_stage_that_moved_the_world_forces_resume_not_replay(tmp_path):
    """Regression for 2 real err 61 failures: a FAILED place still moved the box.

    completed_stage_ids was empty, so the driver chose redispatch and replayed the
    original plan - which the composite rejected because initial_objects no longer held.
    """
    _w(tmp_path / "task.out", _result(outcome=1, error_code=62,
                                      detail="native terminal/verification unconfirmed",
                                      completed_stage_ids=[]))
    _w(tmp_path / "plan.json", json.dumps({
        "initial_objects": [{"object_name": "a", "position": [0.22, 0.0, 0.0175]}],
        "stages": [{"stage_id": "a-0", "object_name": "a",
                    "place_pose": [0.12, -0.15, 0.0175]}],
        "clearance_m": 0.05, "position_tolerance_m": 0.02}))
    _place_failure_journal(tmp_path)
    gt = tmp_path / "gt.json"
    # the box really moved, even though no stage committed
    _w(gt, json.dumps({"objects": {"a": [0.116, -0.20, 0.0175, 0.0]}}))
    assert rd.main(["--run", str(tmp_path), "--ground-truth", str(gt)]) == 0
    retry = json.loads((tmp_path / "plan_retry.json").read_text())
    assert retry["initial_objects"][0]["position"] == [0.116, -0.20, 0.0175]
    rec = json.loads((tmp_path / "recovery_decision.json").read_text())
    assert rec["decision"]["action"] == "resume"


def test_unchanged_world_still_allows_a_plain_redispatch(tmp_path):
    _w(tmp_path / "task.out", _result(outcome=1, error_code=62,
                                      detail="native terminal/verification unconfirmed",
                                      completed_stage_ids=[]))
    _w(tmp_path / "plan.json", json.dumps({
        "initial_objects": [{"object_name": "a", "position": [0.22, 0.0, 0.0175]}],
        "stages": [{"stage_id": "a-0", "object_name": "a",
                    "place_pose": [0.12, -0.15, 0.0175]}]}))
    _place_failure_journal(tmp_path)
    gt = tmp_path / "gt.json"
    _w(gt, json.dumps({"objects": {"a": [0.22, 0.0, 0.0175, 0.0]}}))
    assert rd.main(["--run", str(tmp_path), "--ground-truth", str(gt)]) == 0
    rec = json.loads((tmp_path / "recovery_decision.json").read_text())
    assert rec["decision"]["action"] == "redispatch"


def test_original_failure_files_are_not_overwritten(tmp_path):
    original = _result(outcome=1, error_code=62, detail="unconfirmed",
                       completed_stage_ids=[])
    _w(tmp_path / "task.out", original)
    _w(tmp_path / "plan.json", json.dumps({"stages": [
        {"object_name": "a", "place_pose": [0.12, -0.15, 0.0175]}]}))
    rd.main(["--run", str(tmp_path)])
    assert (tmp_path / "task.out").read_text() == original


def test_missing_terminal_result_is_not_success(tmp_path):
    _w(tmp_path / "task.out", "no result here")
    assert rd.main(["--run", str(tmp_path)]) == 1
    ev = json.loads((tmp_path / "failure_evidence.json").read_text())
    assert ev["error_code"] is None


def test_retry_budget_exhaustion_produces_no_action(tmp_path):
    _w(tmp_path / "task.out", _result(outcome=1, error_code=61, detail="occupied",
                                      completed_stage_ids=[]))
    _w(tmp_path / "plan.json", json.dumps({"stages": [
        {"object_name": "a", "place_pose": [0.12, -0.15, 0.0175]}]}))
    assert rd.main(["--run", str(tmp_path), "--attempt", "2"]) == 1
    rec = json.loads((tmp_path / "recovery_decision.json").read_text())
    assert rec["decision"]["action"] == "no_recovery"


def test_recovery_record_never_mentions_grading_change(tmp_path):
    _w(tmp_path / "task.out", _result(outcome=1, error_code=61, detail="occupied",
                                      completed_stage_ids=[]))
    _w(tmp_path / "plan.json", json.dumps({"stages": [
        {"object_name": "a", "place_pose": [0.12, -0.15, 0.0175]},
        {"object_name": "b", "place_pose": [0.12, -0.15, 0.0175]}]}))
    rd.main(["--run", str(tmp_path)])
    blob = (tmp_path / "recovery_decision.json").read_text().lower()
    for word in ("tolerance", "threshold", "evaluator"):
        assert word not in blob, word
