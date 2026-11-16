"""The feedback handed to the agent must be the result of running the candidate.

A harness that writes one failure sentence before the run and hands it over six
times looks like real feedback - there is a file, there is a failure in it - but
it carries no information, so the agent retries blindly. That version existed,
and it made the mismatched-feedback condition and the no-feedback condition
indistinguishable from the real-feedback one. Measured, same slot, same model:

    static feedback  6 interactions  13,647 tokens  BUDGET_EXHAUSTED
    real feedback    1 interaction      475 tokens  ACCEPT
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for path in (str(HERE), str(HERE.parents[1])):
    if path not in sys.path:
        sys.path.insert(0, path)

import run_matrix_real as R  # noqa: E402


def _candidate(tmp_path, body):
    root = tmp_path / "candidate"
    (root / "skill").mkdir(parents=True)
    (root / "skill" / "__init__.py").write_text("")
    (root / "skill" / "mod.py").write_text(body)
    (root / "skill" / "test_mod.py").write_text(
        "from skill.mod import value\n\n\ndef test_value():\n    assert value() == 7\n")
    return root


def test_feedback_reports_the_real_failure_then_the_real_success(tmp_path):
    root = _candidate(tmp_path, "def value():\n    return 0\n")

    first = R.refresh_feedback(root)
    log = (root / "telemetry" / "execution.log").read_text()
    assert first.returncode != 0
    assert "exit=" in log and "test_value" in log, log

    (root / "skill" / "mod.py").write_text("def value():\n    return 7\n")
    second = R.refresh_feedback(root)
    fixed = (root / "telemetry" / "execution.log").read_text()
    assert second.returncode == 0
    assert "exit=0" in fixed


def test_the_log_changes_between_a_failure_and_a_success(tmp_path):
    """The thing that was broken: the text stayed the same forever."""
    root = _candidate(tmp_path, "def value():\n    return 0\n")
    R.refresh_feedback(root)
    before = (root / "telemetry" / "execution.log").read_text()
    (root / "skill" / "mod.py").write_text("def value():\n    return 7\n")
    R.refresh_feedback(root)
    after = (root / "telemetry" / "execution.log").read_text()
    assert before != after, "the feedback text never changed; it is not from an execution"


def test_the_agent_exposes_the_record_a_custom_driver_needs():
    """Driving step() by hand must not force a second copy of the record shape."""
    import inspect
    import agent
    assert hasattr(agent.RepairAgent, "result")
    params = inspect.signature(agent.RepairAgent.result).parameters
    assert "exhausted" in params
