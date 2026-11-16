"""The pre-registered instances must be runnable and their gate must discriminate.

The first version of the F1 gate passed when no real object was registered -
which is exactly the injected state - so an unrepaired slot would have been
graded a pass. That is the failure these tests exist to prevent: each instance is
checked from both sides, broken and repaired, and the answers must differ.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for path in (str(HERE), str(HERE.parents[1])):
    if path not in sys.path:
        sys.path.insert(0, path)

import instances as I  # noqa: E402


def test_each_instance_fails_its_gate_before_any_repair(tmp_path):
    for family in I.FAMILIES:
        root = tmp_path / family
        I.materialize(family, root)
        ok, payload = I.check(family, root)
        assert not ok, (family, payload)


def test_each_instance_passes_its_gate_after_the_reference_repair(tmp_path):
    for family in I.FAMILIES:
        root = tmp_path / family
        I.materialize(family, root)
        I.apply_reference_fix(family, root)
        ok, payload = I.check(family, root)
        assert ok, (family, payload)


def test_the_gate_discriminates_for_every_instance(tmp_path):
    """Passing everything and failing everything are the same defect."""
    for family in I.FAMILIES:
        root = tmp_path / family
        I.materialize(family, root)
        broken, _ = I.check(family, root)
        I.apply_reference_fix(family, root)
        fixed, _ = I.check(family, root)
        assert (not broken) and fixed, family


def test_f1_injected_config_tracks_no_real_object(tmp_path):
    root = tmp_path / "f1"
    I.materialize("DEF-F1-REG", root)
    text = (root / "config" / "week1.yaml").read_text(encoding="utf-8")
    assert "tracked_objects" in text
    assert "'ghost_object'" in text
    assert "target_box_a" not in text.split("tracked_objects")[1].splitlines()[0]


def test_f2_injected_source_pairs_the_objects_with_the_other_zone(tmp_path):
    root = tmp_path / "f2"
    I.materialize("DEF-F2-MAP", root)
    text = (root / "src" / "task_fsm_server.py").read_text(encoding="utf-8")
    assert "((self._obj_a, 'zone_2'), (self._obj_b, 'zone_1'))" in text


def test_the_gate_lives_outside_the_editable_surface(tmp_path):
    """A repairer must not be able to edit the thing that grades it."""
    for family in I.FAMILIES:
        root = tmp_path / family
        editable = I.materialize(family, root)
        assert not str(editable).startswith(str(root / "gate")), family
        assert (root / "gate" / "check.py").exists()


def test_materialize_writes_the_task_text(tmp_path):
    root = tmp_path / "t"
    I.materialize("DEF-F1-REG", root)
    text = (root / "task.md").read_text(encoding="utf-8")
    assert "config/week1.yaml" in text, "the repairer must be told the editable surface"
