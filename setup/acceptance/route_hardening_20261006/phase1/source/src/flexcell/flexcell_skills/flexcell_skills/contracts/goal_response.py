"""Quarantine a timed-out SendGoal until the same goal is known to be stopped."""
from flexcell_skills.contracts.action_result import AcceptedGoalResult


class LateGoalCleanup:
    """Never resend SendGoal or treat an unknown result as stop confirmation.

    Polling runs after the task has failed. If acceptance arrives late, cancel
    that handle and read its terminal result. Missing acceptance keeps admission
    blocked rather than inventing ownership of an unknown goal.
    """

    def __init__(self, future, emit=None):
        self._future = future
        self._emit = emit or (lambda **fields: None)
        self._result = None
        self._failed = False
        self.resolved = False

    @classmethod
    def after_cancel(cls, result_read, emit=None):
        cleanup = cls(None, emit)
        cleanup._result = result_read
        return cleanup

    def poll(self):
        if self.resolved or self._failed:
            return self.resolved
        try:
            if self._result is None:
                if not self._future.done():
                    return False
                handle = self._future.result()
                if handle is None:
                    raise RuntimeError('late goal acceptance is unknown')
                if not handle.accepted:
                    self._emit(event='late_goal_rejected')
                    self.resolved = True
                    return True
                handle.cancel_goal_async()
                self._result = AcceptedGoalResult(handle)
                self._emit(event='late_goal_cancel_sent')
            if not self._result.done():
                return False
            response = self._result.result()
            if response.status not in (4, 5, 6):
                raise RuntimeError('late goal result is not terminal')
            self._emit(event='late_goal_terminal', status=response.status)
            self.resolved = True
        except Exception as exc:
            self._failed = True
            self._emit(event='late_goal_cleanup_unconfirmed', error=type(exc).__name__)
        return self.resolved
