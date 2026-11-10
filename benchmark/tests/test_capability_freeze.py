#!/usr/bin/env python3
"""Tests for the capability freeze: it must DETECT drift, not just report health."""
import importlib.util
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "freeze_baseline", ROOT / "evolution" / "validation" / "freeze_baseline.py")
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)


def test_baseline_file_exists_and_declares_itself():
    assert F.BASELINE.exists(), "run evolution/validation/freeze_baseline.py"
    doc = json.loads(F.BASELINE.read_text(encoding="utf-8"))
    assert doc["record_kind"] == "EVOBOT_CAPABILITY_BASELINE"
    assert doc["pinned_files"]


def test_every_pinned_file_exists():
    doc = json.loads(F.BASELINE.read_text(encoding="utf-8"))
    assert not doc["missing_pinned_files"], doc["missing_pinned_files"]
    for p in doc["pinned_files"]:
        assert (ROOT / p).exists(), p


def test_the_evaluator_is_actually_pinned():
    """"The ruler" must be in the freeze, or the freeze proves nothing."""
    doc = json.loads(F.BASELINE.read_text(encoding="utf-8"))
    assert "benchmark/evaluators/evaluate.py" in doc["pinned_files"]
    assert "benchmark/evaluators/sealed_evaluate.py" in doc["pinned_files"]


def test_an_unchanged_baseline_verifies():
    ok, problems = F.verify()
    assert ok, problems


def test_drift_in_a_pinned_file_is_detected(monkeypatch, tmp_path):
    """The whole point: if the ruler changes, the freeze must say so."""
    doc = json.loads(F.BASELINE.read_text(encoding="utf-8"))
    # pretend the baseline was taken over a different tree, then corrupt one hash
    fake = dict(doc)
    fake["pinned_files"] = dict(doc["pinned_files"])
    fake["pinned_files"]["benchmark/evaluators/evaluate.py"] = "0" * 64
    bp = tmp_path / "capability_baseline.json"
    bp.write_text(json.dumps(fake), encoding="utf-8")
    monkeypatch.setattr(F, "BASELINE", bp)
    ok, problems = F.verify()
    assert ok is False
    assert any("CHANGED" in p for p in problems)


def test_deleted_pinned_file_is_detected(monkeypatch, tmp_path):
    doc = json.loads(F.BASELINE.read_text(encoding="utf-8"))
    fake = dict(doc)
    fake["pinned_files"] = dict(doc["pinned_files"])
    fake["pinned_files"]["benchmark/evaluators/does_not_exist.py"] = "abc"
    bp = tmp_path / "capability_baseline.json"
    bp.write_text(json.dumps(fake), encoding="utf-8")
    monkeypatch.setattr(F, "BASELINE", bp)
    ok, problems = F.verify()
    assert ok is False
    assert any("deleted" in p for p in problems)

