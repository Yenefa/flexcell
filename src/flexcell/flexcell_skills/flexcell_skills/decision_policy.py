"""DecisionPolicy interface + FSMPolicy (M2.1, issue #4).

The seam frozen by ADR-002: the executor asks the policy WHAT to do next at
every decision point; the executor owns HOW (gate/dispatch/evidence) and the
skills own WHETHER (measured verification).

- `DecisionPolicy.decide(world, goal, constraints, history) -> Decision` is the
  whole interface. Pure function: no IO, no skill calls, no rclpy - offline
  testable by construction.
- `FSMPolicy` reproduces the Week-1.5 demo FSM **by replaying its frozen
  semantics over the decision history**: plan order, RECOVERABLE_PICK
  classification (errors 22/23/30), per-leg retry budget (1 + budget attempts),
  PLACE-failure abort, verify-path reobserve-failure tolerance. Trace
  equivalence (B5) holds by construction: the replay IS the frozen logic.
- History is the ordered record of (decision, typed result) the executor
  feeds back; policies never read logs or any other channel (B1).

Confidence: FSMPolicy is a deterministic rule policy - it emits 1.0 (a rule
verdict, not a probability). Calibration language applies only to
probabilistic policies (Jev/LLM, later per the ratified order).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

# ---------------------------------------------------------------- action menu
ACTION_OBSERVE = 'OBSERVE'
ACTION_PICK = 'PICK'
ACTION_PLACE = 'PLACE'
ACTION_VERIFY = 'VERIFY'
ACTION_WAIT = 'WAIT'
ACTION_ABORT = 'ABORT'
ACTION_ALL = (
    ACTION_OBSERVE, ACTION_PICK, ACTION_PLACE, ACTION_VERIFY,
    ACTION_WAIT, ACTION_ABORT)

# ---------------------------------------------------------------- reason codes
RC_PLAN_NEXT = 'PLAN_NEXT'                        # proceed with the frozen plan
RC_RECOVERABLE_RETRY = 'RECOVERABLE_RETRY'        # pick failed recoverable: REOBSERVE+RETRY
RC_VERIFY_MISMATCH_RETRY = 'VERIFY_MISMATCH_RETRY'  # verify mismatched: REOBSERVE+REVERIFY
RC_BUDGET_EXHAUSTED = 'BUDGET_EXHAUSTED'          # recoverable class, budget spent
RC_VERIFY_BUDGET_EXHAUSTED = 'VERIFY_BUDGET_EXHAUSTED'
RC_NON_RECOVERABLE = 'NON_RECOVERABLE'            # error class recovery cannot fix
RC_OBSERVE_FAILED = 'OBSERVE_FAILED'              # leg-start / recovery observe failed

OUTCOME_NONE = 255                                # no typed outcome (plumbing failure)

# PickObject error codes a REOBSERVE+RETRY may plausibly fix (frozen set,
# moved verbatim from task_fsm_server.py:308).
RECOVERABLE_PICK_ERRORS = frozenset({22, 23, 30})


class PolicyStateError(RuntimeError):
    """The decision history does not match the policy's own decision pattern."""


# ---------------------------------------------------------------- dataclasses
@dataclass(frozen=True)
class EvidenceRef:
    """Attached by the EXECUTOR when logging a decision (the policy cannot
    know world revisions or evidence ids - it only decides)."""
    policy: str
    policy_version: str
    world_revision: int = 0
    observe_evidence_id: str = ''
    decide_latency_ms: int = 0


@dataclass(frozen=True)
class Decision:
    action: str                    # one of ACTION_*
    target: str                    # object_id (leg-scoped); '' when n/a
    confidence: float = 1.0        # [0,1]; rule policies emit 1.0
    reason_code: str = RC_PLAN_NEXT
    explanation: str = ''          # write-only: logged, never parsed (ADR-002)
    evidence_ref: EvidenceRef | None = None


@dataclass(frozen=True)
class TaskGoal:
    goal_id: str
    scenario_id: str
    assignments: tuple             # ((object_id, zone_id), ...) in plan order


@dataclass(frozen=True)
class Constraints:
    allowed_actions: frozenset     # executor-owned menu (B2/B3)
    recovery_budget: int           # hard cap; executor accounts, policy consumes
    verify_tolerance_m: float
    motion_profile_id: str         # whitelist key only
    max_world_age_s: float


@dataclass(frozen=True)
class HistoryRecord:
    """One (decision, typed result) pair, executor-recorded."""
    action: str
    target: str
    outcome: int                   # typed skill outcome; OUTCOME_NONE on plumbing failure
    error_code: int
    attempt: int
    world_revision: int
    evidence_id: str


# ---------------------------------------------------------------- interface
class DecisionPolicy(ABC):
    """ADR-002 decision layer seam. Implementations: FSMPolicy now;
    JevPolicy / LLMPolicy / HybridRouter later (ratified order)."""

    name = 'abstract'
    version = '0'

    @abstractmethod
    def decide(self, world, goal, constraints, history) -> Decision:
        """world: latest WorldState msg (None before the first observe);
        history: ordered tuple of HistoryRecord. Pure - same inputs (and seed)
        must give the same decision."""


# ---------------------------------------------------------------- FSMPolicy
class FSMPolicy(DecisionPolicy):
    """Deterministic replay policy: the Week-1.5 demo FSM as decisions.

    decide() replays the frozen demo procedure over `history` and returns the
    next decision at the point where history ends:
      per leg (plan order): OBSERVE -> PICK(attempt<=1+budget, recoverable
      errors 22/23/30 -> REOBSERVE+RETRY) -> PLACE (failure aborts) ->
      VERIFY(attempt<=1+budget, any mismatch -> REOBSERVE+REVERIFY; the
      reobserve result is ignored - frozen behavior).
    Completion is NOT a decision: the executor finishes the task when every
    assignment is verified (structural check), so decide() is never called
    with all legs complete.
    """

    name = 'fsm'
    version = '1.0'

    def decide(self, world, goal, constraints, history) -> Decision:
        h = list(history)
        idx = 0
        for object_id, zone_id in goal.assignments:
            # ---- leg-start OBSERVE ----
            if idx >= len(h):
                return Decision(ACTION_OBSERVE, object_id,
                                reason_code=RC_PLAN_NEXT,
                                explanation='plan order: leg start')
            rec = h[idx]
            if rec.action != ACTION_OBSERVE:
                raise PolicyStateError(
                    'expected leg-start OBSERVE for %s, got %s'
                    % (object_id, rec.action))
            idx += 1
            if rec.outcome != 0:
                return Decision(ACTION_ABORT, object_id,
                                reason_code=RC_OBSERVE_FAILED,
                                explanation='leg-start observe failed')

            # ---- PICK with bounded recovery ----
            attempt = 1
            while True:
                if idx >= len(h):
                    return Decision(ACTION_PICK, object_id,
                                    reason_code=RC_PLAN_NEXT,
                                    explanation='pick attempt %d' % attempt)
                rec = h[idx]
                if rec.action != ACTION_PICK:
                    raise PolicyStateError(
                        'expected PICK for %s, got %s' % (object_id, rec.action))
                idx += 1
                if rec.outcome == 0:
                    break
                recoverable = (rec.outcome != OUTCOME_NONE
                               and rec.error_code in RECOVERABLE_PICK_ERRORS)
                if not recoverable or (attempt - 1) >= constraints.recovery_budget:
                    return Decision(
                        ACTION_ABORT, object_id,
                        reason_code=(RC_BUDGET_EXHAUSTED if recoverable
                                     else RC_NON_RECOVERABLE),
                        explanation='pick attempt %d failed (error %d)'
                                    % (attempt, rec.error_code))
                # recovery: REOBSERVE then retry
                if idx >= len(h):
                    return Decision(ACTION_OBSERVE, object_id,
                                    reason_code=RC_RECOVERABLE_RETRY,
                                    explanation='recoverable pick failure, budget %d/%d'
                                                % (attempt - 1, constraints.recovery_budget))
                rec = h[idx]
                if rec.action != ACTION_OBSERVE:
                    raise PolicyStateError(
                        'expected recovery REOBSERVE for %s, got %s'
                        % (object_id, rec.action))
                idx += 1
                if rec.outcome != 0:
                    return Decision(ACTION_ABORT, object_id,
                                    reason_code=RC_OBSERVE_FAILED,
                                    explanation='recovery reobserve failed')
                attempt += 1

            # ---- PLACE (failure aborts: carried box, frozen semantics) ----
            if idx >= len(h):
                return Decision(ACTION_PLACE, object_id,
                                reason_code=RC_PLAN_NEXT,
                                explanation='plan order: place')
            rec = h[idx]
            if rec.action != ACTION_PLACE:
                raise PolicyStateError(
                    'expected PLACE for %s, got %s' % (object_id, rec.action))
            idx += 1
            if rec.outcome != 0:
                return Decision(ACTION_ABORT, object_id,
                                reason_code=RC_NON_RECOVERABLE,
                                explanation='place failed (carried box is not retried)')

            # ---- VERIFY with bounded re-verification ----
            vattempt = 1
            while True:
                if idx >= len(h):
                    return Decision(ACTION_VERIFY, object_id,
                                    reason_code=RC_PLAN_NEXT,
                                    explanation='verify attempt %d' % vattempt)
                rec = h[idx]
                if rec.action != ACTION_VERIFY:
                    raise PolicyStateError(
                        'expected VERIFY for %s, got %s' % (object_id, rec.action))
                idx += 1
                if rec.outcome == 0:
                    break  # leg complete
                if (vattempt - 1) >= constraints.recovery_budget:
                    return Decision(ACTION_ABORT, object_id,
                                    reason_code=RC_VERIFY_BUDGET_EXHAUSTED,
                                    explanation='verify still mismatched after budget')
                # recovery: REOBSERVE then re-verify; the reobserve result is
                # IGNORED (frozen behavior) - the re-verify decides.
                if idx >= len(h):
                    return Decision(ACTION_OBSERVE, object_id,
                                    reason_code=RC_VERIFY_MISMATCH_RETRY,
                                    explanation='verify mismatch, budget %d/%d'
                                                % (vattempt - 1, constraints.recovery_budget))
                rec = h[idx]
                if rec.action != ACTION_OBSERVE:
                    raise PolicyStateError(
                        'expected verify-recovery REOBSERVE for %s, got %s'
                        % (object_id, rec.action))
                idx += 1
                vattempt += 1

        raise PolicyStateError(
            'all plan legs already complete - the executor should have '
            'finished the task without calling decide()')
