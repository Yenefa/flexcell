"""Verified skill lifecycle for the task FSM.

A cancel REQUEST is not a stop CONFIRMATION.  This module turns one skill
dispatch into an explicit lifecycle and keeps a sticky quarantine when the
stop cannot be proven:

    DISPATCHED -> ACCEPTED -> EXECUTING -> CANCEL_REQUESTED -> STOP_CONFIRMED
                                      --> STOP_UNCONFIRMED -> QUARANTINED

The stop-confirmation proof itself is NOT reimplemented here: the skills
already run MoveToPose five-way stop proof and answer OUTCOME_STATE_UNKNOWN
when they cannot prove the robot stopped.  The FSM only has to (a) really wait
for the downstream goal to terminate and (b) treat "no terminal result" or
"state unknown" as unconfirmed.
"""
import threading
import time

DISPATCHED = "DISPATCHED"
ACCEPTED = "ACCEPTED"
EXECUTING = "EXECUTING"
CANCEL_REQUESTED = "CANCEL_REQUESTED"
STOP_CONFIRMED = "STOP_CONFIRMED"
STOP_UNCONFIRMED = "STOP_UNCONFIRMED"
QUARANTINED = "QUARANTINED"

OUTCOME_STATE_UNKNOWN = 3
ERR_STATE_UNKNOWN = 33


def _is_state_unknown(result):
    if result is None:
        return True
    outcome = getattr(result, "outcome", None)
    code = getattr(result, "error_code", None)
    return outcome == OUTCOME_STATE_UNKNOWN or code == ERR_STATE_UNKNOWN


def _wait(future, timeout_s, clock, sleep):
    deadline = clock() + max(0.0, timeout_s)
    while not future.done() and clock() < deadline:
        sleep(0.02)
    return future.done()


def confirm_stop(goal_handle, result_reader, cancel_timeout_s=4.0,
                 result_timeout_s=12.0, clock=time.monotonic, sleep=time.sleep):
    """Ask the skill to stop and PROVE that its goal terminated."""
    rec = {"cancel_requested": False, "cancel_accepted": False,
           "cancel_detail": "", "terminated": False,
           "result_outcome": None, "result_error_code": None,
           "result_detail": "", "result_already_done": False,
           "stop_confirmed": False, "reason": ""}

    if result_reader is not None and result_reader.done():
        rec["result_already_done"] = True
        rec["terminated"] = True
    else:
        try:
            if goal_handle is None:
                rec["reason"] = "no goal handle: cancellation cannot be requested"
                return rec
            rec["cancel_requested"] = True
            cancel_future = goal_handle.cancel_goal_async()
            if not _wait(cancel_future, cancel_timeout_s, clock, sleep):
                rec["cancel_detail"] = "no cancel response within %.1fs" % cancel_timeout_s
            else:
                response = cancel_future.result()
                canceling = list(getattr(response, "goals_canceling", None) or [])
                rec["cancel_accepted"] = bool(canceling)
                rec["cancel_detail"] = ("accepted(%d)" % len(canceling) if canceling
                                        else "rejected or no matching executing goal")
        except Exception as exc:  # noqa: BLE001
            rec["cancel_detail"] = "cancel request failed: %s" % exc

        if result_reader is not None:
            rec["terminated"] = _wait(result_reader, result_timeout_s, clock, sleep)

    if rec["terminated"] and result_reader is not None:
        try:
            result = result_reader.result().result
        except Exception as exc:  # noqa: BLE001
            rec["reason"] = "terminal result unreadable: %s" % exc
            return rec
        rec["result_outcome"] = int(getattr(result, "outcome", -1))
        rec["result_error_code"] = int(getattr(result, "error_code", -1))
        rec["result_detail"] = str(getattr(result, "detail", ""))[:400]
        if _is_state_unknown(result):
            rec["reason"] = "terminal result reports STATE_UNKNOWN"
            return rec
        if rec["cancel_accepted"] or rec["result_already_done"]:
            rec["stop_confirmed"] = True
            rec["reason"] = "goal terminated with a known result"
        else:
            rec["reason"] = "goal terminated but the cancel was not accepted"
        return rec

    rec["reason"] = "goal did not terminate: stop unconfirmed"
    return rec


class MotionQuarantine:
    """Sticky gate: while active, no new arm motion may be dispatched."""

    def __init__(self):
        self._lock = threading.Lock()
        self._record = None

    @property
    def active(self):
        with self._lock:
            return self._record is not None

    def record(self):
        with self._lock:
            return dict(self._record) if self._record else None

    def enter(self, **fields):
        """Enter quarantine once; later entries keep the first record."""
        with self._lock:
            if self._record is None:
                fields.setdefault("entered_monotonic", time.monotonic())
                fields.setdefault("operator_reset", False)
                self._record = fields
            return dict(self._record)

    def clear(self, operator):
        """Verified recovery: only when the quarantined goal is known terminated."""
        with self._lock:
            if self._record is None:
                return False, "no active quarantine"
            if not self._record.get("terminated"):
                return False, ("the quarantined goal never reported a terminal "
                               "result: physical intervention is required")
            self._record = None
            return True, "quarantine cleared by %s" % operator
