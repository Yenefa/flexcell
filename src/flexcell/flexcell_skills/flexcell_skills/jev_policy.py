"""JevPolicy + the pluggable JevBackend interface (issue #10, ratified ④).

Jev is a fast classification-style decision model (TypeSafe AI's Choice
primitive, or an APUS-style local reproduction): given the canonical world
state and a Choice question over the allowed-action menu, it returns the top
choice with a probability.  The probability is a ROUTING SIGNAL until
calibrated (issue #1 caveat on vendor numbers) — never a safety property.

Ratified contract (WEEK2_PREPARATION §3 decision table + §5):

- backend-agnostic: JevPolicy talks to the `JevBackend` interface only;
  `TypeSafeBackend` (official SDK) and `LocalReproductionBackend` (APUS-style
  local model) are pluggable implementations (jev_backends.py).
- state payload = the EXACT canonical WorldState envelope bytes (§4.4: the
  same bytes every consumer sees — fair-bytes rule), never a re-rendering.
- parse / OOV (out-of-vocabulary choice) / timeout / backend-unreachable ->
  typed `policy_failure` -> **FSM fallback** (§4.5 gate 4: degradation, not
  deadlock — every cell must complete on FSM-fallback alone).
- the safety gate (#6) still guards every Jev proposal before dispatch: a
  Jev proposal outside the executor's contract is rejected and counted, not
  trusted (issue #1 acceptance item).
- confidence is propagated as reported; threshold routing is HybridRouter's
  job (#12), deliberately NOT this policy's.

Pure module: no rclpy; the backend is injected, so decide() is hermetic
w.r.t. the robot (offline testable by construction, ADR-002).
"""

import json
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace

from flexcell_skills.confidence_calibration import ConfidenceCalibration
from flexcell_skills.canonical_state import serialize_envelope
from flexcell_skills.decision_policy import (
    ACTION_ABORT, ACTION_OBSERVE, ACTION_PICK, ACTION_PLACE, ACTION_VERIFY, Decision,
    FSMPolicy, PolicyStateError)

POLICY_FAILURE = 'policy_failure'


# ---------------------------------------------------------------- backend API
@dataclass(frozen=True)
class ChoiceOption:
    """One candidate in a Choice question (vendor 'Choice' primitive shape:
    a candidate set with per-option criteria)."""
    action: str            # exact action token the policy can accept
    criteria: str          # per-option criteria text (deterministic)


@dataclass(frozen=True)
class ChoiceQuestion:
    prompt: str
    context: str           # compact deterministic task context (last result,
                           # attempt counts - write-only, logged not parsed)
    options: tuple         # (ChoiceOption, ...)


@dataclass(frozen=True)
class JevResponse:
    choice: str            # the backend's selected option action token
    probability: float     # backend-reported confidence (uncalibrated)
    raw: dict = field(default_factory=dict)   # telemetry: tokens/latency/...


class JevBackend(ABC):
    """Pluggable Jev backend (ratified ④).  Implementations: TypeSafeBackend
    (official SDK, region-blocked today, kept pluggable) and
    LocalReproductionBackend (APUS-style local model)."""

    name = 'abstract'

    @abstractmethod
    def health(self):
        """(ok: bool, detail: str) — cheap reachability/configuration probe."""

    @abstractmethod
    def classify(self, state: str, question: ChoiceQuestion) -> JevResponse:
        """One Choice call.  `state` is the EXACT canonical envelope bytes.
        Implementations must honour their own timeouts and raise on failure
        (JevPolicy maps every failure to policy_failure -> FSM fallback)."""


# ---------------------------------------------------------------- policy
def _choice_options(constraints, goal, history):
    """Deterministic Choice menu over the executor-owned action menu (B2/B3),
    with per-option criteria text and the pending-leg context."""
    last = history[-1] if history else None
    attempts = {}
    for h in history:
        attempts[(h.action, h.target)] = attempts.get((h.action, h.target), 0) + 1
    ctx = (
        'last result: %s/%s outcome=%s error=%s; attempts=%s'
        % (last.action if last else '-', last.target if last else '-',
           last.outcome if last else '-', last.error_code if last else '-',
           json.dumps({'%s:%s' % k: v for k, v in sorted(attempts.items())},
                       sort_keys=True))
    ) if history else 'task start (no history)'
    ctx += '; goal=%s; budget=%d; history=%s' % (
        json.dumps(list(goal.assignments)), constraints.recovery_budget,
        json.dumps([{'action': h.action, 'target': h.target,
                     'outcome': h.outcome, 'error_code': h.error_code,
                     'attempt': h.attempt} for h in history], sort_keys=True))
    pending = _pending_target(goal, history)
    by_kind = {
        'OBSERVE': 'gather fresh world state (leg start or after a failure)',
        'PICK': 'pick %s (attempt %d)' % (
            pending, attempts.get(('PICK', pending), 0) + 1),
        'PLACE': 'place the carried object into its assigned zone',
        'VERIFY': 'verify the placed object at its zone',
        'WAIT': 'no-op wait',
        'ABORT': 'abort the task (typed failure)',
    }
    options = tuple(
        ChoiceOption(action=a, criteria=by_kind.get(a, 'allowed action'))
        for a in sorted(constraints.allowed_actions))
    return ctx, options


def _pending_target(goal, history):
    """Plan-order target resolution: the first assignment without a VERIFY
    success.  (Jev chooses the ACTION; the pending leg is deterministic
    bookkeeping, not decision logic.)"""
    verified = set()
    for h in history:
        if h.action == 'VERIFY' and h.outcome == 0:
            verified.add(h.target)
    for obj, _zone in goal.assignments:
        if obj not in verified:
            return obj
    return goal.assignments[0][0] if goal.assignments else ''


class JevPolicy:
    """Fast-path policy: backend Choice over the action menu, FSM fallback on
    any failure.  Same decide() contract as every other DecisionPolicy."""

    name = 'jev'
    version = '1.1'

    def __init__(self, backend, fallback=None, timeout_s=2.0):
        self._backend = backend
        self._fallback = fallback if fallback is not None else FSMPolicy()
        self._timeout_s = float(timeout_s)
        self._calibration = ConfidenceCalibration()
        self.stats = {
            'invocations': 0, 'fallbacks': 0, 'parse_errors': 0,
            'backend_errors': 0, 'no_world': 0, 'tokens': 0,
        }

    def _state_bytes(self, world):
        """The EXACT canonical envelope bytes (fair-bytes rule, §4.4)."""
        if world is None:
            return None
        if isinstance(world, dict):
            # replay form: the already-parsed canonical envelope
            return json.dumps(world, sort_keys=True, separators=(',', ':'))
        # live form: the WorldState msg
        return serialize_envelope(world)

    def decide(self, world, goal, constraints, history):
        state_bytes = self._state_bytes(world)
        if state_bytes is None:
            # pre-observe: the fast path has no state to classify; the
            # deterministic fallback owns leg starts
            self.stats['no_world'] += 1
            return self._fallback_decision(world, goal, constraints, history,
                                           'no world state', '')

        self.stats['invocations'] += 1
        ctx, options = _choice_options(constraints, goal, history)
        question = ChoiceQuestion(
            prompt='Next task-level action for a robotic pick-and-place workcell?',
            context=ctx, options=options)
        valid = {o.action for o in options}

        try:
            resp = self._backend.classify(state_bytes, question)
        except Exception as exc:  # noqa: BLE001 - typed policy_failure
            self.stats['backend_errors'] += 1
            return self._fallback_decision(world, goal, constraints, history,
                                           'backend error', repr(exc))

        try:
            probability = float(resp.probability)
            if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
                raise ValueError('confidence outside [0,1]')
        except (TypeError, ValueError) as exc:
            self.stats['parse_errors'] += 1
            return self._fallback_decision(world, goal, constraints, history,
                                           'invalid confidence', str(exc))
        raw = resp.raw if isinstance(resp.raw, dict) else {}
        self.stats['tokens'] += int(raw.get('tokens', 0) or 0)
        choice = str(resp.choice or '').strip()
        if choice not in valid:
            # OOV / unparseable choice: never passed down (the safety gate
            # would reject it anyway) - typed policy_failure -> FSM fallback
            self.stats['parse_errors'] += 1
            return self._fallback_decision(world, goal, constraints, history,
                                           'oov choice', repr(choice))

        action = choice
        target = (_pending_target(goal, history)
                  if action in (ACTION_OBSERVE, ACTION_PICK, ACTION_PLACE,
                                ACTION_VERIFY) else '')
        reason_code = 'PLAN_NEXT'
        try:
            reference = self._fallback.decide(world, goal, constraints, history)
            if reference.action == action:
                reason_code = reference.reason_code
        except PolicyStateError:
            pass
        reported = probability
        probability, calibrated, calibration = self._calibration.estimate(reported)
        return Decision(
            action=action, target=target,
            confidence=probability,
            reason_code=reason_code,
            policy_trace={'source': self.name, 'fallback': False,
                          'backend': self._backend.name,
                          'model': raw.get('model'),
                          'model_sha256': raw.get('model_sha256'),
                          'reported_confidence': reported,
                          'confidence_calibrated': calibrated,
                          'calibration': calibration,
                          'confidence_label': 'FSM_ACTION_AGREEMENT',
                          'tokens': int(raw.get('tokens', 0) or 0)},
            explanation='jev backend=%s prob=%.3f raw=%s'
                        % (self._backend.name, float(resp.probability),
                           json.dumps(raw, sort_keys=True)[:200]))

    def _fallback_decision(self, world, goal, constraints, history, reason,
                           detail):
        """§4.5 gate 4: degradation, not deadlock.  The FSM baseline decides;
        the typed policy_failure rides in the explanation (write-only, logged
        - never parsed)."""
        self.stats['fallbacks'] += 1
        try:
            d = self._fallback.decide(world, goal, constraints, history)
        except PolicyStateError:
            d = Decision(ACTION_ABORT, '', reason_code='POLICY_FAILURE',
                         explanation='history outside FSM fallback grammar')
        return replace(
            d, explanation='%s %s (%s): %s' % (self.name, POLICY_FAILURE, reason, detail),
            policy_trace={'source': 'fsm', 'fallback': True,
                          'requested_policy': self.name, 'failure': reason})
