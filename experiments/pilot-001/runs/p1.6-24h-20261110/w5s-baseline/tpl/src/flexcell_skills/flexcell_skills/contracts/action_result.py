"""Read one accepted action's result without resending its physical goal."""

import time


class AcceptedGoalResult:
    """Retry the idempotent GetResult request within the caller's deadline.

    Executors keep their existing timeout and cancellation policy. A result
    reply lost in transport must not make an already finished skill look busy.
    This helper only calls get_result_async on the same accepted goal handle.
    """

    def __init__(self, goal_handle, retry_interval_s=5.0, clock=None):
        self._goal = goal_handle
        self._clock = clock or time.monotonic
        if retry_interval_s <= 0:
            raise ValueError('result read retry interval must be positive')
        self._interval = retry_interval_s
        self._next_read = self._clock() + retry_interval_s
        self._reads = [goal_handle.get_result_async()]

    @property
    def request_count(self):
        return len(self._reads)

    def done(self):
        if any(future.done() for future in self._reads):
            return True
        now = self._clock()
        if now >= self._next_read:
            self._reads.append(self._goal.get_result_async())
            self._next_read = now + self._interval
        return any(future.done() for future in self._reads)

    def result(self):
        for future in self._reads:
            if future.done():
                response = future.result()
                if response is None or getattr(response, 'status', None) == 0:
                    raise RuntimeError('accepted action goal result is unknown')
                return response
        raise RuntimeError('accepted action goal result is not ready')
