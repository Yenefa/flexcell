"""Late acceptance is canceled on its original handle; unknown ownership blocks."""
from types import SimpleNamespace

import pytest

from flexcell_skills.contracts.goal_response import LateGoalCleanup


class Future:
    def __init__(self, response=None, done=False):
        self.response = response
        self.ready = done

    def done(self):
        return self.ready

    def result(self):
        return self.response


class Handle:
    accepted = True

    def __init__(self):
        self.cancels = 0
        self.reads = 0
        self.reply = Future()

    def cancel_goal_async(self):
        self.cancels += 1

    def get_result_async(self):
        self.reads += 1
        return self.reply


def test_missing_acceptance_keeps_admission_quarantined():
    cleanup = LateGoalCleanup(Future())
    for _ in range(20):
        assert not cleanup.poll()


@pytest.mark.parametrize('status', [4, 5, 6])
def test_late_acceptance_cancels_once_and_waits_for_terminal_result(status):
    handle = Handle()
    send = Future(handle)
    events = []
    cleanup = LateGoalCleanup(send, lambda **event: events.append(event))
    assert not cleanup.poll()
    send.ready = True
    assert not cleanup.poll()
    assert handle.cancels == handle.reads == 1
    assert not cleanup.poll()
    handle.reply.response = SimpleNamespace(status=status, result='stopped')
    handle.reply.ready = True
    assert cleanup.poll()
    assert cleanup.poll()
    assert handle.cancels == handle.reads == 1
    assert [event['event'] for event in events] == ['late_goal_cancel_sent', 'late_goal_terminal']


def test_confirmed_late_rejection_releases_quarantine():
    cleanup = LateGoalCleanup(Future(SimpleNamespace(accepted=False), done=True))
    assert cleanup.poll()


@pytest.mark.parametrize('status', [0, 1, 2, 3])
def test_unknown_or_nonterminal_result_never_confirms_stop(status):
    handle = Handle()
    handle.reply = Future(SimpleNamespace(status=status, result='unconfirmed'), done=True)
    cleanup = LateGoalCleanup(Future(handle, done=True))
    assert not cleanup.poll()
    assert not cleanup.poll()


def test_missing_handle_is_unknown_not_a_confirmed_rejection():
    assert not LateGoalCleanup(Future(done=True)).poll()


def test_existing_cancel_wait_does_not_cancel_or_resend_again():
    reply = Future()
    cleanup = LateGoalCleanup.after_cancel(SimpleNamespace(done=reply.done, result=reply.result))
    assert not cleanup.poll()
    reply.response = SimpleNamespace(status=5)
    reply.ready = True
    assert cleanup.poll()
