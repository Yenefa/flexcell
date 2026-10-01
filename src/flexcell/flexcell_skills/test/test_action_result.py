"""Exercise lost result replies without ROS or a second physical dispatch."""

from types import SimpleNamespace

import pytest

from flexcell_skills.contracts.action_result import AcceptedGoalResult


class Future:
    def __init__(self, response=None):
        self.response = response

    def done(self):
        return self.response is not None

    def result(self):
        return self.response


class Goal:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.reads = 0

    def get_result_async(self):
        self.reads += 1
        return next(self.replies)


def test_lost_first_reply_is_read_again_on_same_goal():
    now = [0.0]
    reply = SimpleNamespace(status=4, result='finished skill')
    goal = Goal([Future(), Future(reply)])
    read = AcceptedGoalResult(goal, clock=lambda: now[0])
    assert not read.done()
    now[0] = 4.9
    assert not read.done()
    assert goal.reads == 1
    now[0] = 5.0
    assert read.done()
    assert read.result() is reply
    assert goal.reads == 2
    # The handle has no send_goal method: result recovery cannot dispatch.


def test_late_first_reply_wins_without_waiting_for_second():
    now = [0.0]
    first = Future()
    goal = Goal([first, Future()])
    read = AcceptedGoalResult(goal, clock=lambda: now[0])
    now[0] = 5.0
    assert not read.done()
    reply = SimpleNamespace(status=6, result='typed failure')
    first.response = reply
    assert read.done()
    assert read.result() is reply
    now[0] = 20.0
    assert read.done()
    assert goal.reads == 2


def test_unknown_result_is_rejected():
    read = AcceptedGoalResult(Goal([Future(SimpleNamespace(status=0, result='default'))]))
    assert read.done()
    with pytest.raises(RuntimeError, match='unknown'):
        read.result()


def test_reads_are_rate_limited_during_missing_replies():
    now = [0.0]
    goal = Goal([Future(), Future(), Future()])
    read = AcceptedGoalResult(goal, clock=lambda: now[0])
    for value in (5.0, 5.1, 5.2, 9.9, 10.0):
        now[0] = value
        assert not read.done()
    assert read.request_count == 3
