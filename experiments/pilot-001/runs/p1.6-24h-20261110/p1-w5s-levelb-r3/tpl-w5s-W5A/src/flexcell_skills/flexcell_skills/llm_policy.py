"""Slow task reasoning policy, independently implemented at the ADR-002 seam.

The model sees the complete typed goal/constraints/history and canonical world,
then proposes an action AND target with a typed reason. The executor remains
responsible for gating and dispatch. This is distinct from Jev's Choice menu.
"""
import json
import math
import os
import time
import urllib.request
from urllib.parse import urlparse
from dataclasses import replace
from pathlib import Path

from flexcell_skills.canonical_state import serialize_envelope
from flexcell_skills.contracts.episode import constraints_to_record, goal_to_dict, history_to_dicts
from flexcell_skills.decision_policy import (
    ACTION_ABORT, Decision, DecisionPolicy, FSMPolicy, PolicyStateError)
from flexcell_skills.inference_budget import InferenceBudget

REASONS = ('PLAN_NEXT', 'RECOVERABLE_RETRY', 'VERIFY_MISMATCH_RETRY',
           'BUDGET_EXHAUSTED', 'VERIFY_BUDGET_EXHAUSTED', 'NON_RECOVERABLE',
           'OBSERVE_FAILED')


class LLMPolicy(DecisionPolicy):
    name = 'llm'
    version = '2.3'

    def __init__(self, transport=None, fallback=None, timeout_s=None):
        self._transport = transport or self._http
        self._endpoint = os.environ.get('FLEXCELL_LLM_ENDPOINT', '')
        self._model = os.environ.get('FLEXCELL_LLM_MODEL', 'local-slow')
        self._fallback = fallback or FSMPolicy()
        self._timeout_s = float(timeout_s if timeout_s is not None else
                                os.environ.get('FLEXCELL_LLM_TIMEOUT_S', '5'))
        self._response_format = os.environ.get('FLEXCELL_LLM_RESPONSE_FORMAT', 'json_schema')
        self._thinking = os.environ.get('FLEXCELL_LLM_THINKING', '')
        self._max_tokens = int(os.environ.get('FLEXCELL_LLM_MAX_TOKENS', '160'))
        self._backend = os.environ.get('FLEXCELL_LLM_BACKEND', 'local-task-reasoner')
        if (not math.isfinite(self._timeout_s) or self._timeout_s <= 0
                or self._max_tokens <= 0 or self._response_format not in ('json_schema', 'json_object')
                or self._thinking not in ('', 'enabled', 'disabled')):
            raise ValueError('invalid LLM backend configuration')
        self.stats = dict(invocations=0, fallbacks=0, tokens=0, backend_errors=0,
                          parse_errors=0, no_world=0)

    @staticmethod
    def _http(url, payload, timeout):
        if not url:
            raise RuntimeError('FLEXCELL_LLM_ENDPOINT not configured')
        headers = {'Content-Type': 'application/json', 'User-Agent': 'flexcell/1.0'}
        key_file = os.environ.get('FLEXCELL_LLM_API_KEY_FILE')
        if key_file:
            if not url.startswith('https://'):
                raise ValueError('authenticated LLM endpoint requires HTTPS')
            key = Path(key_file).read_text().strip()
            if not key:
                raise ValueError('empty LLM credential')
            headers['Authorization'] = 'Bearer ' + key
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
        budget_path = os.environ.get('FLEXCELL_LLM_BUDGET_FILE')
        budget = InferenceBudget(budget_path) if budget_path else None
        call_id = budget.reserve(url, payload) if budget else None
        opener = (urllib.request.build_opener(urllib.request.ProxyHandler({}))
                  if urlparse(url).hostname in ('localhost', '127.0.0.1', '::1')
                  else None)
        open_request = opener.open if opener else urllib.request.urlopen
        with open_request(req, timeout=timeout) as reply:
            response = json.load(reply)
        if budget:
            response['_flexcell_cost'] = budget.settle(call_id, response)
        return response

    def decide(self, world, goal, constraints, history):
        if world is None:
            self.stats['no_world'] += 1
            return self._degrade(world, goal, constraints, history, 'bootstrap')
        canonical = (json.dumps(world, sort_keys=True, separators=(',', ':'),
                                ensure_ascii=False) if isinstance(world, dict)
                     else serialize_envelope(world))
        context = {'goal': goal_to_dict(goal), 'constraints': constraints_to_record(constraints),
                   'history': history_to_dicts(history)}
        latest = context['history'][-1] if history else None
        prompt = (
            'Decide one next action to complete this robotic task. Reason from the typed '
            'history and current world. Outcomes: 0=SUCCEEDED, 1=FAILED, 255=no result; '
            'error 0 means success. For each assigned object use OBSERVE -> PICK -> '
            'PLACE -> VERIFY. After successful OBSERVE choose PICK, without repeating '
            'OBSERVE. After successful PICK choose PLACE. After successful PLACE choose '
            'VERIFY. After successful VERIFY start the next unfinished object with OBSERVE. '
            'A successful retry completes PICK even when an earlier PICK failed. '
            'Read the most recent history result first. Old failures and old object poses '
            'must not override a later success. If carry.engaged is true, do not PICK again. '
            'Use allowed_actions in constraints; target is an object, not a zone. Verify '
            'after place. A failed pick with errors 22/23/30 may be reobserved and retried '
            'within the recovery budget. A failed PLACE is not retried while carrying. '
            'Abort when recovery is exhausted. Track completed objects individually. '
            'Do not infer that failed motion succeeded. Return only a JSON decision with '
            'action, target, confidence, reason_code, explanation (one short sentence). Target is an assigned '
            'object id, or empty for WAIT/ABORT. Allowed reason_code values: %s.\n'
            'LATEST RESULT (authoritative):\n%s\nTASK (typed):\n%s\nWORLD (canonical, verbatim):\n%s'
            % (','.join(REASONS), json.dumps(latest, sort_keys=True),
               json.dumps(context, sort_keys=True), canonical))
        payload = {'model': self._model, 'temperature': 0.0, 'max_tokens': self._max_tokens,
                   'seed': 20260930}
        if self._thinking:
            payload['thinking'] = {'type': self._thinking}
        if self._endpoint.endswith('/chat/completions'):
            payload['messages'] = [{'role': 'user', 'content': prompt}]
            payload['response_format'] = {'type': 'json_schema', 'json_schema': {
                'name': 'task_decision', 'strict': True, 'schema': {
                    'type': 'object', 'properties': {
                        'action': {'type': 'string', 'enum': sorted(constraints.allowed_actions)},
                        'target': {'type': 'string', 'enum': sorted({o for o, _ in goal.assignments} | {''})},
                        'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1},
                        'reason_code': {'type': 'string', 'enum': list(REASONS)},
                        'explanation': {'type': 'string'}},
                    'required': ['action', 'target', 'confidence', 'reason_code', 'explanation'],
                    'additionalProperties': False}}}
            if self._response_format == 'json_object':
                payload['response_format'] = {'type': 'json_object'}
        else:
            payload['prompt'] = prompt
        self.stats['invocations'] += 1
        t0 = time.perf_counter_ns()
        try:
            reply = self._transport(self._endpoint, payload, self._timeout_s)
        except Exception as exc:
            self.stats['backend_errors'] += 1
            d = self._degrade(world, goal, constraints, history, 'backend_error')
            trace = dict(d.policy_trace, error_type=type(exc).__name__,
                         http_status=getattr(exc, 'code', None))
            return replace(d, policy_trace=trace)
        try:
            choice = reply['choices'][0]
            content = choice.get('text') or choice.get('message', {}).get('content')
            proposed = json.loads(content)
            action, target = proposed['action'], proposed['target']
            confidence = float(proposed['confidence'])
            reason = proposed['reason_code']
            if (action not in constraints.allowed_actions or not isinstance(target, str)
                    or target not in {o for o, _ in goal.assignments} | {''}
                    or reason not in REASONS or not math.isfinite(confidence)
                    or not 0 <= confidence <= 1 or choice.get('finish_reason') == 'length'):
                raise ValueError('out-of-contract LLM decision')
            usage = reply.get('usage') or {}
            tokens = int(usage.get('total_tokens', 0) or 0)
            self.stats['tokens'] += tokens
            return Decision(action, target, confidence, reason,
                            str(proposed.get('explanation', ''))[:300],
                            policy_trace={'source': 'llm', 'fallback': False,
                                          'backend': self._backend,
                                          'model': self._model, 'tokens': tokens,
                                          'response_model': reply.get('model'),
                                          'response_format': self._response_format,
                                          'thinking': self._thinking or 'backend-default',
                                          'finish_reason': choice.get('finish_reason'),
                                          'cost': reply.get('_flexcell_cost'),
                                          'prompt_tokens': usage.get('prompt_tokens'),
                                          'completion_tokens': usage.get('completion_tokens'),
                                          'backend_latency_ms': (time.perf_counter_ns() - t0) / 1e6})
        except (KeyError, TypeError, ValueError, IndexError):
            self.stats['parse_errors'] += 1
            return self._degrade(world, goal, constraints, history, 'parse_error')

    def _degrade(self, world, goal, constraints, history, reason):
        self.stats['fallbacks'] += 1
        try:
            d = self._fallback.decide(world, goal, constraints, history)
        except PolicyStateError:
            d = Decision(ACTION_ABORT, '', reason_code='POLICY_FAILURE',
                         explanation='history outside FSM fallback grammar')
        return replace(d, policy_trace={'source': 'fsm', 'fallback': True,
                                       'requested_policy': 'llm', 'failure': reason})
