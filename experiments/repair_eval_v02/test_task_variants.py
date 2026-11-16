"""v2 withholds the answer from the task and puts it in the feedback channel.

v1 named the objects to register, so the no-feedback condition could repair
without any feedback and every condition passed F1. v2 states the symptom only;
the names travel with the execution feedback, which B, C and D may read and A
may not.

These tests hold both halves: the task text really is silent, and the channel
that carries the answer is really closed for A.
"""
import json
import pytest
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
for path in (str(HERE), str(HERE.parents[1]),
             str(HERE.parents[1] / "benchmark" / "repair_eval" / "contracts")):
    if path not in sys.path:
        sys.path.insert(0, path)

import instances as I                               # noqa: E402
from benchmark.repair_eval import visibility as vis  # noqa: E402


def _check(family, variant):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "c"
        I.materialize(family, root, variant)
        return I.check(family, root, variant)


def test_v1_names_the_answer_and_v2_does_not():
    v1 = I.task_text("DEF-F1-REG", "v1")
    v2 = I.task_text("DEF-F1-REG", "v2")
    assert "target_box_a" in v1 and "target_box_b" in v1
    assert "target_box_a" not in v2 and "target_box_b" not in v2


def test_v2_puts_the_names_in_the_feedback_where_a_condition_may_read_them():
    _ok, v1_payload = _check("DEF-F1-REG", "v1")
    _ok, v2_payload = _check("DEF-F1-REG", "v2")
    assert "expected_objects" not in v1_payload
    assert sorted(v2_payload.get("expected_objects") or []) == ["target_box_a", "target_box_b"]


def test_a_passing_repair_reports_no_extra_information():
    """The channel must not leak the answer once the repair is correct."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "c"
        I.materialize("DEF-F1-REG", root, "v2")
        I.apply_reference_fix("DEF-F1-REG", root)
        ok, payload = I.check("DEF-F1-REG", root, "v2")
    assert ok is True
    assert "expected_objects" not in payload


def test_condition_a_cannot_read_the_channel_that_carries_the_answer():
    """This is what makes v2 a real contrast rather than a wording change."""
    policy = vis.load_policy(Path(HERE.parents[1]) / "benchmark" / "repair_eval"
                             / "visibility_policy.json")
    assert policy.conditions["A_STATIC"].visible["execution_feedback"] is False
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        root = I.materialize("DEF-F1-REG", tmp / "candidate", "v2")
        (root / "telemetry").mkdir(exist_ok=True)
        (root / "telemetry" / "execution.log").write_text(
            json.dumps({"code": "OBJECT_NOT_REGISTERED",
                        "expected_objects": ["target_box_a", "target_box_b"]}))
        verdict = tmp / "verdict"; verdict.mkdir()
        hidden = tmp / "hidden"; hidden.mkdir()
        boundary = vis.RunBoundary(policy, tmp, root, verdict, hidden,
                                   condition="A_STATIC", mismatch_dir=None)
        denied = getattr(vis, "AccessDenied", None)
        with pytest.raises(Exception) as caught:
            boundary.read_feedback()
        # assert the reason, not just that something went wrong: a
        # FileNotFoundError would satisfy a bare raises() and hide the fact
        # that the channel had been readable.
        message = str(caught.value)
        assert "execution_feedback" in message, message
        if denied is not None:
            assert isinstance(caught.value, denied), type(caught.value)


def test_an_unknown_variant_is_refused():
    try:
        I.task_text("DEF-F1-REG", "v3")
    except ValueError as exc:
        assert "variant" in str(exc)
        return
    raise AssertionError("an unknown variant was accepted")
