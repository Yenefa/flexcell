"""Frozen artifacts, complete regressions, and an independently chosen reference."""
import json
from pathlib import Path
import shutil
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evaluate_holdout as E
import evidence_archive as ARCH
import frozen_regressions as REG
import health
import holdout as H
import instances as I


def archive(tmp_path, name, fix=True):
    work = tmp_path / (name + "-work")
    I.materialize("DEF-F1-REG", work / "candidate", "v2")
    shutil.copytree(work / "candidate", work / "initial_candidate")
    if fix:
        I.apply_reference_fix("DEF-F1-REG", work / "candidate")
    dest = tmp_path / name
    ARCH.preserve(work, dest, {"slot_id": name, "instance": "DEF-F1-REG",
                             "qualification": "MECHANICAL_TEST", "task_variant": "v2",
                             "source_sha": "a" * 40, "selection_basis": "test fixture"})
    return dest


def frozen_pair(tmp_path, *, candidate_fix=True, reference_fix=False):
    candidate = archive(tmp_path, "candidate", candidate_fix)
    reference = archive(tmp_path, "reference", reference_fix)
    freeze = tmp_path / "freeze.json"
    E.create_freeze(candidate, reference, freeze, selection_basis="test chosen before evaluation",
                    reference_basis="predeclared test reference", mechanical=True, repair_runs=24)
    return candidate, reference, freeze


def test_comparison_and_all_seven_regressions_are_retained_for_both_artifacts(tmp_path):
    candidate, reference, freeze = frozen_pair(tmp_path)
    report = E.evaluate(freeze, tmp_path / "evaluation")
    assert report["comparison_complete"] and report["regression_complete"]
    assert len(report["comparison"]) == 6
    assert all(r["candidate"] == "PASS" and r["reference"] == "FAIL"
               for r in report["comparison"])
    for arm in ("candidate", "reference"):
        cases = report["regressions"][arm]
        assert [r["case_id"] for r in cases] == ["N1", "N2", "N3", "N4", "N5", "N6", "P1"]
        assert all(r["status"] == "PASS" for r in cases)
        # Correct negative-case rejection is a passing regression, never FAIL.
        assert cases[0]["actual_status"] == "REJECT"
        assert cases[-1]["actual_status"] == "ACCEPT"
    assert report["counts"]["holdout_executions"] == 6
    assert report["counts"]["reference_executions"] == 6
    assert report["counts"]["repair_runs"] == 24
    assert report["mechanical_only"]
    assert report["gate_independent"] == "NOT_RUN"
    assert health.tree_sha(candidate / "candidate") == report["candidate_sha"]


def test_reference_is_not_implicitly_assumed_to_fail(tmp_path):
    _, _, freeze = frozen_pair(tmp_path, candidate_fix=False, reference_fix=True)
    report = E.evaluate(freeze, tmp_path / "evaluation")
    assert all(r["candidate"] == "FAIL" and r["reference"] == "PASS"
               for r in report["comparison"])
    assert not report["checks_passed"]


def test_formal_path_refuses_reference_repair_as_model_candidate(tmp_path):
    candidate = archive(tmp_path, "candidate")
    reference = archive(tmp_path, "reference")
    with pytest.raises(H.HoldoutError, match="model candidate"):
        E.create_freeze(candidate, reference, tmp_path / "freeze.json",
                        selection_basis="before", reference_basis="before")


@pytest.mark.parametrize("arm", ("candidate", "reference"))
def test_changing_either_frozen_artifact_is_refused_before_any_slot(tmp_path, arm):
    candidate, reference, freeze = frozen_pair(tmp_path)
    chosen = candidate if arm == "candidate" else reference
    (chosen / "candidate" / "config" / "week1.yaml").write_text("changed after freeze")
    with pytest.raises(ValueError, match="changed"):
        E.evaluate(freeze, tmp_path / "evaluation")
    assert not (tmp_path / "evaluation").exists()


def test_missing_case_is_a_retained_failure_and_remaining_cases_still_execute(tmp_path):
    candidate = archive(tmp_path, "candidate")
    cases = tmp_path / "cases"
    shutil.copytree(REG.CASES, cases)
    (cases / REG.CASE_FILES[2]).unlink()
    results = REG.run(candidate / "candidate", health.tree_sha(candidate / "candidate"), cases)
    assert len(results) == 7
    assert results[2]["case_id"] == "N3" and results[2]["status"] == "FAIL"
    assert results[-1]["status"] == "PASS"


def test_wrong_oracle_answer_is_retained_as_fail_in_report(tmp_path, monkeypatch):
    _, _, freeze = frozen_pair(tmp_path)
    original = REG.casefile.run

    def wrong(case):
        result = original(case)
        if result["case_id"] == "N4":
            result.update(status_ok=False, actual_status="ACCEPT", false_accept=True)
        return result

    monkeypatch.setattr(REG.casefile, "run", wrong)
    report = E.evaluate(freeze, tmp_path / "evaluation")
    assert all(next(r for r in rows if r["case_id"] == "N4")["status"] == "FAIL"
               for rows in report["regressions"].values())
    assert not report["checks_passed"]
    saved = json.loads((tmp_path / "evaluation" / "report.json").read_text())
    assert saved["regressions"]["candidate"][3]["false_accept"]


def test_reference_result_requires_correct_sha_time_and_once_only():
    freeze = H.Freeze("a" * 64, "run", "before", frozen_at=10,
                      reference_sha="b" * 64, reference_basis="baseline commit")
    plan = H.HoldoutPlan(("L1", "L2"), ("s1", "s2", "s3"), freeze)
    for sha, at in (("a" * 64, 11), ("b" * 64, 9)):
        with pytest.raises(H.HoldoutError):
            plan.record("L1|s1", "PASS", arm="reference", evaluated_sha=sha, at=at)
    plan.record("L1|s1", "FAIL", arm="reference", evaluated_sha="b" * 64, at=11)
    with pytest.raises(H.HoldoutError):
        plan.record("L1|s1", "PASS", arm="reference", evaluated_sha="b" * 64, at=12)
    assert plan.report()["comparison"][0]["reference"] == "FAIL"
    with pytest.raises(H.HoldoutError):
        freeze.reference_sha = "c" * 64


def test_hardcoded_geometry_cannot_be_transferred_over_a_different_layout():
    with pytest.raises(ValueError, match="uniquely"):
        E.transfer_edit("x: 0.12\nobjects: []\n", "x: 0.25\nobjects: [a]\n",
                        "x: 0.31\nobjects: []\n")
