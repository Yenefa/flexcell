"""The pre-registered instances must be runnable and their gate must discriminate.

The first version of the F1 gate passed when no real object was registered -
which is exactly the injected state - so an unrepaired slot would have been
graded a pass. That is the failure these tests exist to prevent: each instance is
checked from both sides, broken and repaired, and the answers must differ.
"""
import json
import sys
import tempfile
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
        I.materialize(family, root)
        editable = I.editable_path(family, root)
        assert not str(editable).startswith(str(root / "gate")), family
        assert (root / "gate" / "check.py").exists()


def test_materialize_writes_the_task_text(tmp_path):
    root = tmp_path / "t"
    I.materialize("DEF-F1-REG", root)
    text = (root / "task.md").read_text(encoding="utf-8")
    assert "config/week1.yaml" in text, "the repairer must be told the editable surface"


# ---------------------------------------------------------------- known defect
def test_the_task_text_still_hands_over_the_answer_known_defect():
    """Characterisation test: this passes today because the defect is real.

    The F1 task text names the two objects the repair has to register, and the F2
    text names the expected pairing. That is why all four conditions came out 3/3
    on F1 and why F2 differed only in search cost: there was nothing left for the
    feedback conditions to supply.

    The test asserts the leak on purpose, so that whoever fixes the task text
    sees a red test naming this file rather than silence. Deleting it without
    changing the texts would hide the defect again; changing the texts turns it
    red and that is the signal to delete it and update DEFECT_DESIGN.md.
    """
    f1 = I.TASK_TEXT["DEF-F1-REG"]
    f2 = I.TASK_TEXT["DEF-F2-MAP"]
    assert "target_box_a" in f1 and "target_box_b" in f1, \
        "F1 no longer leaks the object names - update DEFECT_DESIGN.md and drop this test"
    assert "zone_1" in f2 and "zone_2" in f2, \
        "F2 no longer leaks the expected pairing - update DEFECT_DESIGN.md and drop this test"


def test_the_leak_is_not_in_the_gate_answer_it_is_in_the_question():
    """The names come from task.md, not from the feedback a condition receives.

    No-feedback condition A is given task.md and nothing else, so if it can
    repair F1 the names must have arrived through the task text. That is the
    whole diagnosis, stated as a check on where the information lives.
    """
    f1 = I.TASK_TEXT["DEF-F1-REG"]
    for name in ("target_box_a", "target_box_b"):
        assert name in f1
    # the gate's own answer names only what it saw, not what was expected
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "c"
        I.materialize("DEF-F1-REG", root)
        _ok, payload = I.check("DEF-F1-REG", root)
    assert "target_box_a" not in json.dumps(payload), payload


def test_deleting_the_key_is_not_a_repair():
    """ROS would inherit the node default, and that default happens to be healthy.

    Measured 2026-11-17: with the fallback in place, deleting tracked_objects made
    the gate report PASS with ['target_box_a','target_box_b'] - a repair that
    requires knowing nothing. The acceptance rule is that the configuration states
    the objects, so absence has its own code.
    """
    import re
    with tempfile.TemporaryDirectory() as tmp:
        root = I.materialize("DEF-F1-REG", Path(tmp) / "c", "v2")
        cfg = root / "config" / "week1.yaml"
        cfg.write_text(re.sub(r"\n\s*tracked_objects:.*", "", cfg.read_text()), encoding="utf-8")
        ok, payload = I.check("DEF-F1-REG", root, "v2")
    assert not ok
    assert payload["code"] == "TRACKED_OBJECTS_ABSENT", payload


def test_an_empty_list_and_a_missing_key_are_different_failures():
    import re
    with tempfile.TemporaryDirectory() as tmp:
        root = I.materialize("DEF-F1-REG", Path(tmp) / "c", "v2")
        cfg = root / "config" / "week1.yaml"
        cfg.write_text(re.sub(r"tracked_objects:.*", "tracked_objects: []", cfg.read_text()), encoding="utf-8")
        ok, payload = I.check("DEF-F1-REG", root, "v2")
    assert not ok
    assert payload["code"] == "OBJECT_NOT_REGISTERED", payload
