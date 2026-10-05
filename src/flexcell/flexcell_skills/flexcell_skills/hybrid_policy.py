"""Confidence-gated Jev -> LLM -> FSM routing at the ADR-002 seam (#11/#12).

The router never dispatches skills. Both model proposals pass the same pure
safety gate; the executor gates the selected decision again. Confidence is a
routing signal, with threshold swept as an experiment variable. Provenance
is structured telemetry, never parsed from explanation strings.
"""

import json
import math
from dataclasses import replace

from flexcell_skills.canonical_state import serialize_envelope
from flexcell_skills.contracts.safety_gate import validate
from flexcell_skills.decision_policy import (
    ACTION_ABORT, Decision, DecisionPolicy, FSMPolicy, PolicyStateError)
from flexcell_skills.llm_policy import LLMPolicy  # compatibility re-export


class HybridRouter(DecisionPolicy):
    name = 'hybrid'
    version = '1.1'

    def __init__(self, fast, slow, threshold=0.7, fallback=None, require_calibration=True):
        self._threshold = float(threshold)
        if not math.isfinite(self._threshold) or not 0 <= self._threshold <= 1:
            raise ValueError('hybrid threshold must be finite and in [0,1]')
        self._fast, self._slow = fast, slow
        self._require_calibration = require_calibration
        self._fallback = fallback or FSMPolicy()
        self.stats = dict(invocations=0, fast_selected=0, escalations=0,
                          slow_selected=0, fallbacks=0, rejected_proposals=0,
                          fast_bypassed=0)

    def decide(self, world, goal, constraints, history):
        self.stats['invocations'] += 1
        trace = {'threshold': self._threshold, 'proposals': [],
                 'calibration_sha256': getattr(self._fast, 'calibration_sha256', None)}
        if world is None:
            return self._fallback_decision(world, goal, constraints, history,
                                           trace, 'bootstrap')
        canonical = world if isinstance(world, dict) else json.loads(
            serialize_envelope(world))

        def propose(policy):
            try:
                d = policy.decide(world, goal, constraints, history)
                ok, reason = validate(d, goal, canonical, constraints)
                confidence = float(d.confidence)
                if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                    ok, reason = False, 'invalid_confidence'
                fallback = bool((d.policy_trace or {}).get('fallback'))
                trace['proposals'].append({
                    'policy': policy.name, 'action': d.action,
                    'target': d.target, 'confidence': confidence,
                    'gate_ok': ok, 'gate_reason': reason,
                    'fallback': fallback, 'policy_trace': d.policy_trace})
                if not ok:
                    self.stats['rejected_proposals'] += 1
                return d if ok and not fallback else None
            except Exception as exc:
                trace['proposals'].append({'policy': policy.name,
                                           'failure': type(exc).__name__})
                return None

        eligibility = getattr(self._fast, 'route_eligible', None)
        bypass = bool(self._require_calibration and eligibility and
                      not eligibility(self._threshold))
        if bypass:
            self.stats['fast_bypassed'] += 1
            trace['proposals'].append({'policy': self._fast.name, 'skipped': True,
                                      'reason': 'calibration_unavailable_or_threshold_unattainable'})
            fast = None
        else:
            fast = propose(self._fast)
        calibrated = bool(fast and (fast.policy_trace or {}).get('confidence_calibrated'))
        trace['fast_calibration_required'] = self._require_calibration
        trace['fast_confidence_calibrated'] = calibrated
        if (fast is not None and fast.confidence >= self._threshold
                and (calibrated or not self._require_calibration)):
            self.stats['fast_selected'] += 1
            return replace(fast, policy_trace=dict(trace, source=self._fast.name,
                                                   fallback=False, escalated=False))
        trace['escalation_reason'] = ('calibration_unavailable_or_threshold_unattainable' if bypass
                                      else 'uncalibrated_fast_confidence'
                                      if fast and not calibrated and self._require_calibration
                                      else 'fast_unavailable_or_below_threshold')
        self.stats['escalations'] += 1
        slow = propose(self._slow)
        if slow is not None:
            self.stats['slow_selected'] += 1
            return replace(slow, policy_trace=dict(trace, source=self._slow.name,
                                                   fallback=False, escalated=True))
        return self._fallback_decision(world, goal, constraints, history,
                                       trace, 'both_model_paths_unavailable')

    def _fallback_decision(self, world, goal, constraints, history, trace, reason):
        self.stats['fallbacks'] += 1
        try:
            d = self._fallback.decide(world, goal, constraints, history)
        except PolicyStateError:
            # A model may have produced a history outside the reference FSM's
            # grammar. Fail as a typed task abort instead of pretending replay.
            d = Decision(ACTION_ABORT, '', reason_code='POLICY_FAILURE',
                         explanation='history outside FSM fallback grammar')
        return replace(d, policy_trace=dict(trace, source='fsm', fallback=True,
                                            escalated=reason != 'bootstrap',
                                            failure=reason))
