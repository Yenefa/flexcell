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
import math
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

    def __setattr__(self, name, value):
        if hasattr(self, name):
            raise HoldoutError("freeze fields cannot be changed; create a new version")
        object.__setattr__(self, name, value)

    def __init__(self, candidate_sha, source_run_id, selection_basis,
                 frozen_at=None, repair_runs=0, reference_sha=None,
                 reference_basis=None):
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
        if not isinstance(self.frozen_at, (float, int)) or not math.isfinite(self.frozen_at):
            raise HoldoutError("freeze timestamp must be finite")
        self.repair_runs = repair_runs
        if reference_sha is not None and (not isinstance(reference_sha, str)
                or not reference_sha.strip() or not isinstance(reference_basis, str)
                or not reference_basis.strip()):
            raise HoldoutError("a reference requires its SHA and selection basis")
        self.reference_sha = reference_sha
        self.reference_basis = reference_basis

    def as_dict(self):
        return {"candidate_sha": self.candidate_sha,
                "source_run_id": self.source_run_id,
                "selection_basis": self.selection_basis,
                "frozen_at": self.frozen_at,
                "repair_runs": self.repair_runs,
                "reference_sha": self.reference_sha,
                "reference_basis": self.reference_basis}

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
        self._reference = {}
        self._regressions = {}
        for layout in self.layouts:
            for state in self.initial_states:
                self._slots["%s|%s" % (layout, state)] = NOT_RUN
                self._reference["%s|%s" % (layout, state)] = NOT_RUN

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
                "reference_executions": sum(s in TERMINAL for s in self._reference.values()),
                "holdout_planned": len(self._slots),
                "reported_separately": True}

    # ------------------------------------------------------------ execution
    def record(self, slot_id, outcome, *, evaluated_sha, at=None, arm="candidate"):
        """Write one result, once.

        Refuses a second write: #253 says a failure that triggers a new repair
        starts a new version, and the older result keeps its identity. Allowing
        an overwrite is how a failed row quietly becomes a pass.
        """
        if arm not in ("candidate", "reference"):
            raise HoldoutError("unknown comparison arm")
        slots = self._slots if arm == "candidate" else self._reference
        expected_sha = (self.freeze.candidate_sha if arm == "candidate"
                        else self.freeze.reference_sha)
        if not expected_sha:
            raise HoldoutError("no reference frozen before execution")
        if slot_id not in slots:
            raise HoldoutError("unknown slot %r" % (slot_id,))
        if outcome not in TERMINAL:
            raise HoldoutError("outcome must be one of %s, got %r"
                               % (", ".join(TERMINAL), outcome))
        if slots[slot_id] != NOT_RUN:
            raise HoldoutError(
                "slot %r already recorded as %s; a re-run is a new record, "
                "not an overwrite" % (slot_id, slots[slot_id]))
        if evaluated_sha != expected_sha:
            raise HoldoutError(
                "candidate evaluated (%s) is not the frozen candidate (%s)"
                % (evaluated_sha, expected_sha))
        moment = at if at is not None else time.time()
        if moment < self.freeze.frozen_at:
            # the result predates the freeze: whatever was frozen may have been
            # chosen because of this result
            raise HoldoutError(
                "hold-out result recorded before the candidate was frozen; the "
                "selection could have seen it")
        slots[slot_id] = outcome
        return self.statuses()

    def record_regressions(self, arm, results):
        if arm not in ("candidate", "reference") or arm in self._regressions:
            raise HoldoutError("invalid or already recorded regression arm")
        expected_sha = self.freeze.candidate_sha if arm == "candidate" else self.freeze.reference_sha
        if {r["case_id"] for r in results} != {"N1", "N2", "N3", "N4", "N5", "N6", "P1"} \
                or len(results) != 7 or any(r.get("evaluated_sha") != expected_sha
                                          or r.get("status") not in ("PASS", "FAIL")
                                          for r in results):
            raise HoldoutError("seven candidate-bound fixed regression results required")
        self._regressions[arm] = results

    def report(self):
        statuses = self.statuses()
        comparison = [{"slot_id": slot, "candidate": status,
                       "reference": self._reference[slot]} for slot, status in statuses.items()]
        comparison_complete = bool(self.freeze.reference_sha) and all(
            row[arm] in TERMINAL for row in comparison for arm in ("candidate", "reference"))
        regression_complete = set(self._regressions) == {"candidate", "reference"}
        return {"candidate_sha": self.freeze.candidate_sha,
                "reference_sha": self.freeze.reference_sha,
                "reference_basis": self.freeze.reference_basis,
                "freeze_sha": self.freeze.sha(),
                "source_run_id": self.freeze.source_run_id,
                "selection_basis": self.freeze.selection_basis,
                "counts": self.counts(),
                "slots": statuses,
                "comparison": comparison,
                "comparison_complete": comparison_complete,
                "regressions": self._regressions,
                "regression_complete": regression_complete,
                "checks_passed": comparison_complete and regression_complete and
                    all(s == "PASS" for s in statuses.values()) and
                    all(r["status"] == "PASS" for results in self._regressions.values()
                        for r in results),
                "scope": "only this retained set; no cross-embodiment or hardware inference",
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
