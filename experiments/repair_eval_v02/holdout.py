"""Hold-out discipline for the retained-scenario check (#253).

WHY THIS IS A MODULE AND NOT A SENTENCE
    #253 requires that the candidate be frozen, with a full source SHA, before
    any retained scenario runs, and that "the selection process must not look at
    the retained results". Written as a promise, that rule is unenforceable: by
    the time anyone can tell you peeked, the number is already in the paper.

    Two things are mechanically checkable, and this enforces both:

      1. the candidate SHA the hold-out evaluates is the SHA that was frozen;
      2. the freeze was recorded before the first hold-out result existed.

    The second one is the one that matters. A freeze timestamped after a result
    means whatever was frozen could have been chosen because of that result, and
    no amount of later argument recovers the experiment.

WHAT IT DELIBERATELY DOES NOT DO
    It cannot stop a human from reading the held-out answer key out of band, and
    it does not pretend to. It closes the route that leaves evidence: a freeze
    recorded after the fact, or a candidate swapped in after results are known.
"""
import hashlib
import json
import time


class HoldoutError(Exception):
    """Raised when the hold-out rules are violated."""


NOT_RUN = "NOT_RUN"
TERMINAL = ("PASS", "FAIL", "INVALID")


def digest(payload):
    """Stable digest of a JSON-able payload."""
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)
    return hashlib.sha256(body.encode()).hexdigest()


class Freeze:
    """The record that says which candidate was fixed before the hold-out ran."""

    def __init__(self, candidate_sha, source_run_id, selection_basis,
                 frozen_at=None, repair_runs=0):
        for name, value in (("candidate_sha", candidate_sha),
                            ("source_run_id", source_run_id),
                            ("selection_basis", selection_basis)):
            if not isinstance(value, str) or not value.strip():
                raise HoldoutError("%s must be a non-empty string" % name)
        if not isinstance(repair_runs, int) or repair_runs < 0:
            raise HoldoutError("repair_runs must be a non-negative integer")
        self.candidate_sha = candidate_sha
        self.source_run_id = source_run_id
        self.selection_basis = selection_basis
        self.frozen_at = frozen_at if frozen_at is not None else time.time()
        self.repair_runs = repair_runs

    def as_dict(self):
        return {"candidate_sha": self.candidate_sha,
                "source_run_id": self.source_run_id,
                "selection_basis": self.selection_basis,
                "frozen_at": self.frozen_at,
                "repair_runs": self.repair_runs}

    def sha(self):
        return digest(self.as_dict())


class HoldoutPlan:
    """The 6 planned slots: 2 layouts that took no part in development x 3 states."""

    def __init__(self, layouts, initial_states, freeze):
        if not isinstance(freeze, Freeze):
            raise HoldoutError("a plan requires a freeze, not a candidate on trust")
        if len(layouts) != 2:
            raise HoldoutError("the protocol fixes 2 retained layouts, got %d" % len(layouts))
        if len(initial_states) != 3:
            raise HoldoutError("the protocol fixes 3 initial states, got %d"
                               % len(initial_states))
        self.freeze = freeze
        self.layouts = tuple(layouts)
        self.initial_states = tuple(initial_states)
        self._slots = {}
        for layout in self.layouts:
            for state in self.initial_states:
                self._slots["%s|%s" % (layout, state)] = NOT_RUN

    # ------------------------------------------------------------- planning
    @property
    def slot_ids(self):
        return tuple(self._slots)

    def statuses(self):
        return dict(self._slots)

    def counts(self):
        repair = self.freeze.repair_runs
        holdout = sum(1 for s in self._slots.values() if s in TERMINAL)
        return {"repair_runs": repair, "holdout_executions": holdout,
                "holdout_planned": len(self._slots),
                "reported_separately": True}

    # ------------------------------------------------------------ execution
    def record(self, slot_id, outcome, *, evaluated_sha, at=None):
        """Write one result, once.

        Refuses a second write: #253 says a failure that triggers a new repair
        starts a new version, and the older result keeps its identity. Allowing
        an overwrite is how a failed row quietly becomes a pass.
        """
        if slot_id not in self._slots:
            raise HoldoutError("unknown slot %r" % (slot_id,))
        if outcome not in TERMINAL:
            raise HoldoutError("outcome must be one of %s, got %r"
                               % (", ".join(TERMINAL), outcome))
        if self._slots[slot_id] != NOT_RUN:
            raise HoldoutError(
                "slot %r already recorded as %s; a re-run is a new record, "
                "not an overwrite" % (slot_id, self._slots[slot_id]))
        if evaluated_sha != self.freeze.candidate_sha:
            raise HoldoutError(
                "candidate evaluated (%s) is not the frozen candidate (%s)"
                % (evaluated_sha, self.freeze.candidate_sha))
        moment = at if at is not None else time.time()
        if moment < self.freeze.frozen_at:
            # the result predates the freeze: whatever was frozen may have been
            # chosen because of this result
            raise HoldoutError(
                "hold-out result recorded before the candidate was frozen; the "
                "selection could have seen it")
        self._slots[slot_id] = outcome
        return self.statuses()

    def report(self):
        statuses = self.statuses()
        return {"candidate_sha": self.freeze.candidate_sha,
                "freeze_sha": self.freeze.sha(),
                "source_run_id": self.freeze.source_run_id,
                "selection_basis": self.freeze.selection_basis,
                "counts": self.counts(),
                "slots": statuses,
                "all_terminal": all(s in TERMINAL for s in statuses.values())}


def assert_frozen(freeze, candidate_sha):
    """The gate every hold-out execution must pass through."""
    if not isinstance(freeze, Freeze):
        raise HoldoutError("no freeze recorded; refusing to evaluate a candidate "
                           "that was not fixed in advance")
    if candidate_sha != freeze.candidate_sha:
        raise HoldoutError(
            "candidate %s is not the frozen candidate %s"
            % (candidate_sha, freeze.candidate_sha))
    return True
