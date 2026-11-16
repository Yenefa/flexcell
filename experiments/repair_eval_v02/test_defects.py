"""The pre-registered defect instances must be reproducible and must actually bite.

TASKS.md names DEF-F1-REG and DEF-F2-MAP and leaves their realization to #252.
A manifest with "TBD" in the injection column is not an instance: nothing can be
injected, so the pre-registered slots cannot be run against the defect the
protocol names. These tests hold the two artifacts to three properties each:
the digest in the manifest matches the artifact, applying it produces the stated
fault, and the pristine input really was the healthy one.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFECTS = HERE / "defects"
CONFIG_REL = "src/flexcell/flexcell_skills/config/week1.yaml"
FSM_REL = "src/flexcell/flexcell_skills/flexcell_skills/task_fsm_server.py"


def sha_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def manifest(defect):
    return json.loads((DEFECTS / defect / "manifest.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- F1: config
def test_f1_override_digest_matches_the_manifest():
    info = manifest("DEF-F1-REG")
    assert sha_of(DEFECTS / "DEF-F1-REG" / info["artifact"]) == info["artifact_sha256"]


def test_f1_override_removes_the_registry_but_changes_nothing_else():
    override = (DEFECTS / "DEF-F1-REG" / "override.yaml").read_text(encoding="utf-8")
    pristine = (ROOT / CONFIG_REL).read_text(encoding="utf-8")
    assert "tracked_objects:" in pristine
    assert "tracked_objects:" not in override
    # one line removed, nothing else: same file, minus the registry
    assert len(pristine.splitlines()) - 1 == len(override.splitlines())
    assert sha_of(ROOT / CONFIG_REL) == manifest("DEF-F1-REG")["pristine_sha256"]


def test_f1_override_keeps_the_rest_of_the_config_loadable():
    """Removing the key must not silently mangle the zones the task depends on."""
    yaml = pytest.importorskip("yaml")
    parsed = yaml.safe_load((DEFECTS / "DEF-F1-REG" / "override.yaml").read_text(encoding="utf-8"))
    params = parsed["observe_server"]["ros__parameters"]
    assert "tracked_objects" not in params
    assert params["zones"] == ["zone_1", "zone_2"]
    assert params["zone_zone_1_x"] == 0.12


# ---------------------------------------------------------------- F2: source
def test_f2_patch_digest_matches_the_manifest():
    info = manifest("DEF-F2-MAP")
    assert sha_of(DEFECTS / "DEF-F2-MAP" / info["artifact"]) == info["artifact_sha256"]


def test_f2_patch_applies_to_the_pristine_source(tmp_path):
    target = tmp_path / FSM_REL
    target.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / FSM_REL, target)
    ran = subprocess.run(["patch", "-p1", "--batch", "-i",
                          str(DEFECTS / "DEF-F2-MAP" / "inject.patch")],
                         cwd=tmp_path, capture_output=True, text=True)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    injured = target.read_text(encoding="utf-8")
    assert "((self._obj_a, 'zone_2'), (self._obj_b, 'zone_1'))" in injured
    assert "((self._obj_a, 'zone_1'), (self._obj_b, 'zone_2'))" not in injured


def test_f2_patch_touches_only_the_stated_file():
    info = manifest("DEF-F2-MAP")
    patch = (DEFECTS / "DEF-F2-MAP" / "inject.patch").read_text(encoding="utf-8")
    headers = [l for l in patch.splitlines() if l.startswith("+++ ")]
    assert len(headers) == 1
    assert headers[0].endswith(info["affected_files"][0])


def test_f2_pristine_source_still_carries_the_healthy_mapping():
    assert sha_of(ROOT / FSM_REL) == manifest("DEF-F2-MAP")["pristine_sha256"]
    assert "((self._obj_a, 'zone_1'), (self._obj_b, 'zone_2'))" in \
        (ROOT / FSM_REL).read_text(encoding="utf-8")
