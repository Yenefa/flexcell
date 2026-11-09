"""P0-A reproduction: a cancel request is not a stop confirmation.

These tests drive the REAL production dispatch helper `_demo_call` on a
TaskFsmServer instance.  Only the ROS action-client transport is faked, so the
waits, the cancel handshake and the quarantine gate are the production ones.
"""
import time

import pytest

from flexcell_skills import task_fsm_server as module
from flexcell_skills.skill_lifecycle import MotionQuarantine


class _Future:
    def __init__(self, value=None, done=True):
        self._value = value
        self._done = done

    def done(self):
        return self._done

    def result(self):
        return self._value

    def complete(self, value=None):
        self._value = value
        self._done = True


class _Result:
    def __init__(self, outcome=0, error_code=0, detail=""):
        self.outcome = outcome
        self.error_code = error_code
        self.detail = detail


class _GoalResponse:
    def __init__(self, result):
        self.result = result


class _CancelResponse:
    def __init__(self, canceling):
        self.goals_canceling = list(canceling)


class FakeGoal:
    """Transport-level stand-in for an accepted ROS action goal."""

    def __init__(self, result_future, cancel_response=None, cancel_delay_s=0.0,
                 result_delay_s=0.0, result_value=None):
        self.accepted = True
        self._result_future = result_future
        self._cancel_response = cancel_response
        self._cancel_delay_s = cancel_delay_s
        self._result_delay_s = result_delay_s
        self._result_value = result_value
        self.cancel_calls = 0

    def cancel_goal_async(self):
        self.cancel_calls += 1
        future = _Future(done=False)

        def _finish():
            time.sleep(self._cancel_delay_s)
            future.complete(self._cancel_response)

        import threading
        threading.Thread(target=_finish, daemon=True).start()
        return future

    def get_result_async(self):
        if self._result_delay_s and not self._result_future.done():
            import threading

            def _finish():
                time.sleep(self._result_delay_s)
                self._result_future.complete(_GoalResponse(self._result_value))

            threading.Thread(target=_finish, daemon=True).start()
        return self._result_future


class FakeClient:
    def __init__(self, goal):
        self._goal = goal
        self.sent = 0

    def wait_for_server(self, timeout_sec=0.0):
        return True

    def send_goal_async(self, goal):
        self.sent += 1
        return _Future(self._goal)


def make_node(cancel_timeout_s=0.2, result_timeout_s=0.3):
    node = module.TaskFsmServer.__new__(module.TaskFsmServer)
    node._quarantine = MotionQuarantine()
    node._stop_cancel_timeout_s = cancel_timeout_s
    node._stop_result_timeout_s = result_timeout_s
    node._last_stop = None
    node.task_states = []

    def _publish(msg, *a, **k):
        node.task_states.append(msg.data)

    node._state_pub = type("P", (), {"publish": staticmethod(_publish)})()
    node.get_logger = lambda: type("L", (), {
        "info": staticmethod(lambda *a, **k: None),
        "warn": staticmethod(lambda *a, **k: None),
        "error": staticmethod(lambda *a, **k: None)})()
    return node


def call(node, goal, label="PICK_A", deadline_s=0.1, outer=None):
    if outer is not None and not hasattr(outer, "request"):
        outer.request = module.RunDemo.Goal()
        outer.publish_feedback = lambda fb: None
    cli = FakeClient(goal)
    return node._demo_call(cli, object(), label, outer, time.monotonic(), deadline_s)


def test_normal_completion_needs_no_cancel_or_quarantine():
    result_future = _Future(_GoalResponse(_Result()), done=True)
    goal = FakeGoal(result_future)
    node = make_node()
    result, error = call(node, goal, deadline_s=5.0)
    assert error is None and result.outcome == 0
    assert goal.cancel_calls == 0
    assert not node._quarantine.active


def test_timeout_waits_for_stop_confirmation_before_returning():
    result_future = _Future(done=False)
    goal = FakeGoal(result_future, cancel_response=_CancelResponse([b"x"]),
                    result_delay_s=0.25, result_value=_Result())
    node = make_node(result_timeout_s=1.0)
    started = time.monotonic()
    result, error = call(node, goal, deadline_s=0.05)
    elapsed = time.monotonic() - started
    assert goal.cancel_calls == 1
    assert elapsed >= 0.2, "returned before the stop was confirmed"
    assert not node._quarantine.active
    assert result is not None and result.outcome == 0


def test_accepted_cancel_without_termination_quarantines():
    goal = FakeGoal(_Future(done=False), cancel_response=_CancelResponse([b"x"]))
    node = make_node(result_timeout_s=0.15)
    result, error = call(node, goal, deadline_s=0.05)
    assert result is None
    assert "stop" in error.lower() or "unconfirmed" in error.lower()
    assert node._quarantine.active
    record = node._quarantine.record()
    assert record["cancel_accepted"] is True
    assert record["terminated"] is False


def test_rejected_cancel_that_never_terminates_quarantines():
    goal = FakeGoal(_Future(done=False), cancel_response=_CancelResponse([]))
    node = make_node(result_timeout_s=0.15)
    result, error = call(node, goal, deadline_s=0.05)
    assert result is None and node._quarantine.active
    assert node._quarantine.record()["cancel_accepted"] is False


def test_cancel_response_timeout_quarantines():
    goal = FakeGoal(_Future(done=False), cancel_response=_CancelResponse([b"x"]),
                    cancel_delay_s=0.5)
    node = make_node(cancel_timeout_s=0.1, result_timeout_s=0.15)
    result, error = call(node, goal, deadline_s=0.05)
    assert result is None and node._quarantine.active
    assert "no cancel response" in node._quarantine.record()["cancel_detail"]


def test_unknown_goal_acceptance_quarantines():
    node = make_node()

    class UnknownSend(FakeClient):
        def send_goal_async(self, goal):
            return _Future(done=False)

    cli = UnknownSend(FakeGoal(_Future(done=False)))
    result, error = node._demo_call(cli, object(), "PICK_A", None,
                                    time.monotonic(), 0.05)
    assert result is None
    assert node._quarantine.active
    assert "acceptance" in node._quarantine.record()["reason"]


def test_state_unknown_result_quarantines():
    result_future = _Future(done=False)
    goal = FakeGoal(result_future, cancel_response=_CancelResponse([b"x"]),
                    result_delay_s=0.02,
                    result_value=_Result(outcome=3, error_code=33,
                                         detail="stop unconfirmed"))
    node = make_node(result_timeout_s=1.0)
    result, error = call(node, goal, deadline_s=0.05)
    assert result is None and node._quarantine.active
    assert node._quarantine.record()["result_outcome"] == 3


def test_outer_cancel_waits_and_quarantines_when_unconfirmed():
    goal = FakeGoal(_Future(done=False), cancel_response=_CancelResponse([b"x"]))
    node = make_node(result_timeout_s=0.15)
    outer = type("G", (), {"is_cancel_requested": True})()
    result, error = call(node, goal, deadline_s=5.0, outer=outer)
    assert result is None and node._quarantine.active


def test_quarantine_blocks_next_dispatch_and_survives_clear_until_terminated():
    node = make_node(result_timeout_s=0.1)
    goal = FakeGoal(_Future(done=False), cancel_response=_CancelResponse([b"x"]))
    call(node, goal, deadline_s=0.05)
    assert node._quarantine.active
    ok, detail = node._quarantine.clear("test")
    assert not ok and "terminal" in detail


def test_verified_reset_clears_a_terminated_quarantine():
    record = {"terminated": True, "cancel_accepted": True, "reason": "test"}
    node = make_node()
    node._quarantine.enter(**record)
    ok, detail = node._quarantine.clear("operator")
    assert ok and "operator" in detail
    assert not node._quarantine.active


def test_quarantine_keeps_lease_and_never_reports_idle():
    node = make_node()
    node._admission = __import__("threading").Lock()
    node._admission.acquire()
    node._quarantine.enter(terminated=False, reason="test")
    node._finish_arm_state(True)
    assert node._admission.locked(), "lease released while stop was unconfirmed"
    assert node.task_states[-1] == "QUARANTINED"
    assert "IDLE" not in node.task_states


def test_normal_finish_releases_lease_and_reports_idle():
    node = make_node()
    node._admission = __import__("threading").Lock()
    node._admission.acquire()
    node._finish_arm_state(True)
    assert not node._admission.locked()
    assert node.task_states[-1] == "IDLE"


def test_pending_skill_goal_is_true_while_quarantined():
    node = make_node()
    assert node._has_pending_skill_goal() is False
    node._quarantine.enter(terminated=False, reason="test")
    assert node._has_pending_skill_goal() is True


def test_reset_refuses_until_the_goal_is_known_terminated():
    node = make_node()
    node._admission = __import__("threading").Lock()
    node._admission.acquire()
    node._quarantine.enter(terminated=False, reason="test")
    response = type("R", (), {})()
    out = node._reset_motion_quarantine(None, response)
    assert out.success is False and node._admission.locked()
    assert node._quarantine.active


def test_verified_reset_releases_the_quarantined_lease():
    node = make_node()
    node._admission = __import__("threading").Lock()
    node._admission.acquire()
    node._quarantine.enter(terminated=True, reason="terminated")
    response = type("R", (), {})()
    out = node._reset_motion_quarantine(None, response)
    assert out.success is True
    assert not node._admission.locked() and node.task_states[-1] == "IDLE"
