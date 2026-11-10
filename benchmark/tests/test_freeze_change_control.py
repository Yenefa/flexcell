#!/usr/bin/env python3
"""Tests that re-freezing REQUIRES a documented reason.

The freeze is only worth something if changing a pinned file is hard. The first version of
freeze_baseline.py could simply be re-run to overwrite the baseline, which would make every
drift check decorative. It now refuses unless docs/FREEZE_CHANGELOG.md names the file.
"""
import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "fb", ROOT / "evolution" / "validation" / "freeze_baseline.py")
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)


def test_the_changelog_exists_and_names_the_recent_change():
    log = F._changelog()
    assert log, "docs/FREEZE_CHANGELOG.md is missing"
    assert "observe_from_run.py" in log
    # a reason must be stated, not just a filename
    assert "为什么" in log or "why" in log.lower()


def test_the_baseline_records_what_changed_and_why_it_matters():
    doc = json.loads(F.BASELINE.read_text(encoding="utf-8"))
    assert doc["record_kind"] == "EVOBOT_CAPABILITY_BASELINE"
    # the change is recorded in the baseline itself, so a reader sees it without git
    assert "changes_since_previous" in doc


def test_changed_pinned_detects_a_tampered_hash(monkeypatch, tmp_path):
    doc = json.loads(F.BASELINE.read_text(encoding="utf-8"))
    fake = dict(doc)
    fake["pinned_files"] = dict(doc["pinned_files"])
    fake["pinned_files"]["benchmark/evaluators/evaluate.py"] = "0" * 64
    bp = tmp_path / "capability_baseline.json"
    bp.write_text(json.dumps(fake), encoding="utf-8")
    monkeypatch.setattr(F, "BASELINE", bp)
    changes = F.changed_pinned()
    assert any(p == "benchmark/evaluators/evaluate.py" for p, _, _, _ in changes)


def test_no_changes_reported_when_everything_matches():
    assert F.changed_pinned() == []


def test_refreeze_refuses_when_the_changelog_omits_the_file(monkeypatch, tmp_path):
    doc = json.loads(F.BASELINE.read_text(encoding="utf-8"))
    fake = dict(doc)
    fake["pinned_files"] = dict(doc["pinned_files"])
    fake["pinned_files"]["benchmark/schemas/taskspec.schema.json"] = "1" * 64
    bp = tmp_path / "capability_baseline.json"
    bp.write_text(json.dumps(fake), encoding="utf-8")
    log = tmp_path / "FREEZE_CHANGELOG.md"
    log.write_text("nothing relevant here", encoding="utf-8")
    monkeypatch.setattr(F, "BASELINE", bp)
    monkeypatch.setattr(F, "REQUIRED_REASON", log)
    try:
        F.freeze()
    except SystemExit as exc:
        assert "REFUSING" in str(exc)
    else:
        raise AssertionError("freeze() overwrote a changed pinned file without a reason")
