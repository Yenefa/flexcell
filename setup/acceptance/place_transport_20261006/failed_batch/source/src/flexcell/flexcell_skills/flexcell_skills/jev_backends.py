"""Pluggable Jev backends (issue #10, ratified ④).

Two implementations of the `JevBackend` interface (WEEK2_PREPARATION §5):

- `TypeSafeBackend` — the official TypeSafe AI SDK (`typesafe-sdk`,
  `client.system_one(state=..., questions={...})` shape).  Region-blocked
  from mainland China today (ratified: remote = NO on this network), so this
  class is import-guarded and reports health-unavailable when the SDK or the
  service is absent.  It exists so the vendor integration point is typed and
  ready, never bound to.
- `LocalReproductionBackend` — the APUS-style local reproduction: a local
  OpenAI-compatible completion endpoint that returns a single structured
  choice (single-token logits / short decode are the server's concern; this
  client consumes the response contract below).  Transport is INJECTED so
  offline tests script it; the default transport reads FLEXCELL_JEV_ENDPOINT
  / FLEXCELL_JEV_MODEL from the environment.

Response contract (local backend): the completion text is JSON
    {"choice": "<one of the option action tokens>", "confidence": <0..1>,
     "tokens": <int, optional>}
Anything else is a parse failure (JevPolicy maps it to policy_failure ->
FSM fallback).

No vendor secret, key, or endpoint is ever committed (workspace rule).
"""

import json
import os
import socket
import urllib.error
import urllib.request
from urllib.parse import urlparse

from flexcell_skills.jev_policy import JevBackend, JevResponse


class TypeSafeBackend(JevBackend):
    """Official TypeSafe AI SDK backend (kept pluggable; region-blocked today)."""

    name = 'typesafe'

    def __init__(self, api_key_env='TYPESAFE_API_KEY'):
        self._api_key = os.environ.get(api_key_env, '')
        self._client = None

    def _sdk(self):
        """Import-guarded vendor client (never a hard dependency)."""
        if self._client is None:
            try:
                import typesafe_sdk  # noqa: F401 - vendor SDK, absent here
                self._client = typesafe_sdk.client(
                    api_key=self._api_key or None)
            except ImportError as exc:
                raise RuntimeError(
                    'typesafe-sdk not installed (region-blocked; kept '
                    'pluggable per ratified ④): %s' % exc) from exc
        return self._client

    def health(self):
        try:
            self._sdk()
        except RuntimeError as exc:
            return False, str(exc)
        return True, 'sdk present (service reachability untested)'

    def classify(self, state, question):
        client = self._sdk()
        questions = {
            'next_action': {
                'prompt': question.prompt,
                'context': question.context,
                'options': {o.action: o.criteria for o in question.options},
            },
        }
        rep = client.system_one(state=json.loads(state),
                                questions=questions)
        return JevResponse(
            choice=str(getattr(rep, 'choice', '') or ''),
            probability=float(getattr(rep, 'probability', 0.0) or 0.0),
            raw={'backend': self.name})


class LocalReproductionBackend(JevBackend):
    """APUS-style local model behind an OpenAI-compatible completion endpoint.

    `transport` is injected: a callable (url, payload, timeout_s) -> parsed
    JSON dict.  Tests script it; production uses the default urllib transport
    against FLEXCELL_JEV_ENDPOINT (e.g. a single-node vLLM/llama.cpp server
    running the local reproduction model with logprobs).
    """

    name = 'local-reproduction'

    def __init__(self, transport=None, model=None,
                 endpoint_env='FLEXCELL_JEV_ENDPOINT',
                 model_env='FLEXCELL_JEV_MODEL', timeout_s=None, max_tokens=96):
        self._injected = transport is not None
        self._endpoint = os.environ.get(endpoint_env, '')
        self._model = model or os.environ.get(model_env, 'local-jev')
        self._transport = transport or self._http_transport
        self._endpoint_env = endpoint_env
        self._timeout_s = float(timeout_s if timeout_s is not None else
                                os.environ.get('FLEXCELL_JEV_TIMEOUT_S', '2'))
        self._max_tokens = int(max_tokens)

    @staticmethod
    def _http_transport(url, payload, timeout_s):
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json'})
        opener = (urllib.request.build_opener(urllib.request.ProxyHandler({}))
                  if urlparse(url).hostname in ('localhost', '127.0.0.1', '::1')
                  else None)
        open_request = opener.open if opener else urllib.request.urlopen
        with open_request(req, timeout=timeout_s) as resp:
            return json.loads(resp.read().decode())

    def health(self):
        if not self._endpoint:
            return False, ('%s not set - local server unavailable'
                           % self._endpoint_env)
        return True, 'endpoint configured (reachability checked on decision)'

    def _render(self, state, question):
        """Fixed prompt template: canonical JSON embedded verbatim + the
        numbered Choice menu + the response contract (structured output)."""
        menu = '\n'.join(
            '%d. %s — %s' % (i, o.action, o.criteria)
            for i, o in enumerate(question.options, 1))
        actions = ', '.join(o.action for o in question.options)
        return (
            'You are the task-level decision policy of a robotic workcell.\n'
            'History outcomes: 0=SUCCEEDED, 1=FAILED, 255=no result. Error 0 is success. '
            'For each assigned object use OBSERVE -> PICK -> PLACE -> VERIFY. '
            'After a successful OBSERVE choose PICK, not another OBSERVE. '
            'After a successful PICK choose PLACE; after successful PLACE choose VERIFY. '
            'After successful VERIFY start the next unfinished object with OBSERVE. '
            'A failed PICK with error 22,23,30 permits OBSERVE then PICK within budget. '
            'After failed PLACE choose ABORT. When retry budget is spent choose ABORT. '
            'Use history to track progress; an old source pose does not undo a successful action.\n'
            'WORLD STATE (canonical, verbatim):\n%s\n\n'
            'TASK CONTEXT: %s\n'
            'Choose exactly ONE next action from this menu:\n%s\n'
            'Respond with a single JSON object: '
            '{"choice": "<one of: %s>", "confidence": <0..1>}' % (
                state, question.context, menu, actions))

    def classify(self, state, question):
        if not self._injected and not self._endpoint:
            raise RuntimeError(
                'local reproduction endpoint not configured '
                '(FLEXCELL_JEV_ENDPOINT) - typed policy_failure upstream')
        payload = {
            'model': self._model,
            'prompt': self._render(state, question),
            'max_tokens': self._max_tokens,
            'temperature': 0.0,
        }
        if self._endpoint.endswith('/chat/completions'):
            payload['messages'] = [{'role': 'user', 'content': payload.pop('prompt')}]
            payload['response_format'] = {'type': 'json_object'}
        payload['seed'] = 20260930
        rep = self._transport(self._endpoint, payload, self._timeout_s)
        choice = (rep.get('choices') or [{}])[0]
        text = choice.get('text') or choice.get('message', {}).get('content', '')
        parsed = json.loads(text)
        return JevResponse(
            choice=str(parsed.get('choice', '')),
            probability=float(parsed.get('confidence', 0.0)),
            raw={'backend': self.name,
                 'model': self._model,
                 'model_sha256': (None if self._injected else
                                  os.environ.get('FLEXCELL_JEV_MODEL_SHA256')),
                 'tokens': int(rep.get('usage', {}).get('total_tokens', 0) or 0)})


class ClefBackend(JevBackend):
    """Cloudflare Clef decision model behind a typed /v1/systemone endpoint
    (e.g. Ollama serving the open Apache-2.0 Clef weights, or the hosted
    Workers AI shape).  Clef scores every option of every question in a
    single forward pass and returns probabilities - there is no free-form
    generation to truncate and no JSON to parse, so the failure modes that
    disqualify the generative local reproduction (E-016: 160-token output
    cap, FSM-grammar disagreement) are structurally absent here.

    Same Jev / SystemOne question shape as `TypeSafeBackend.classify`:
    questions = {name: {prompt, context, options: {action: criteria}}}.

    `transport` is injected for offline tests; the default transport POSTs
    {model, state, questions} to the FAST-ARM profile envs (FLEXCELL_JEV_*):
    one profile slot, two swappable implementations, so the calibration-gate
    identity (model + model_sha256, validated by ConfidenceCalibration) stays
    coherent across backends.  The state is forwarded as the exact canonical
    envelope bytes (fair-bytes principle; Clef accepts string or JSON state).
    """

    name = 'clef'

    # Prompt v2: fold the frozen FSM cycle semantics into the instructions and
    # enrich each option's criteria with the rule that disambiguates it (the
    # generative baseline's failures were mostly eager actions: PICK instead of
    # a fresh OBSERVE, skipping VERIFY).  Backend-scoped: the shared
    # _choice_options contract text stays untouched.
    _INSTRUCTIONS_TEMPLATE = (
        'You are the task-level decision policy of a robotic workcell. History '
        'outcomes: 0=SUCCEEDED, 1=FAILED, 255=no result. The per-object action '
        'cycle is strictly OBSERVE -> PICK -> PLACE -> VERIFY; after VERIFY '
        'succeeds, start the next unfinished object with OBSERVE. After a '
        'successful OBSERVE choose PICK, not another OBSERVE. After a '
        'successful PICK choose PLACE; after a successful PLACE choose VERIFY. '
        'A failed PICK with error 22, 23 or 30 permits OBSERVE then PICK '
        'within the retry budget; after a failed PLACE or a spent budget '
        'choose ABORT. An old source pose does not undo a successful action. '
        'Context: %s'
    )
    _CRITERIA_ENRICHMENT = {
        'OBSERVE': 'refresh the world snapshot; also the correct next step '
                   'when the previous PICK failed with error 22, 23 or 30',
        'PICK': 'the object is observed in the world snapshot and the gripper '
                'is empty; not a retry of a just-failed grasp before a fresh '
                'OBSERVE',
        'PLACE': 'the gripper is carrying an object right now',
        'VERIFY': 'the object was just placed; confirms the placement, do not '
                  'skip it',
        'ABORT': 'retry budget spent, PLACE failed, or the task is '
                 'unrecoverable',
    }

    def __init__(self, transport=None, model=None,
                 endpoint_env='FLEXCELL_JEV_ENDPOINT',
                 model_env='FLEXCELL_JEV_MODEL', timeout_s=None):
        self._injected = transport is not None
        self._endpoint = os.environ.get(endpoint_env, '')
        self._model = model or os.environ.get(model_env, 'clef-flash')
        self._transport = transport or self._http_transport
        self._endpoint_env = endpoint_env
        self._timeout_s = float(timeout_s if timeout_s is not None else
                                os.environ.get('FLEXCELL_JEV_TIMEOUT_S', '2'))

    @staticmethod
    def _http_transport(url, payload, timeout_s):
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json'})
        opener = (urllib.request.build_opener(urllib.request.ProxyHandler({}))
                  if urlparse(url).hostname in ('localhost', '127.0.0.1', '::1')
                  else None)
        open_request = opener.open if opener else urllib.request.urlopen
        with open_request(req, timeout=timeout_s) as resp:
            return json.loads(resp.read().decode())

    def health(self):
        if not self._endpoint:
            return False, ('%s not set - clef endpoint unavailable'
                           % self._endpoint_env)
        if self._injected:
            return True, 'injected transport (network not probed)'
        try:
            endpoint = urlparse(self._endpoint)
            if endpoint.scheme not in ('http', 'https') or not endpoint.hostname:
                raise ValueError('invalid HTTP endpoint')
            port = endpoint.port or (443 if endpoint.scheme == 'https' else 80)
            with socket.create_connection((endpoint.hostname, port),
                                          timeout=min(self._timeout_s, 2.0)):
                pass
        except (OSError, ValueError) as exc:
            return False, 'TCP endpoint unavailable: %s' % type(exc).__name__
        return True, 'TCP reachable (typed inference checked on decision)'

    def classify(self, state, question):
        if not self._injected and not self._endpoint:
            raise RuntimeError(
                'clef endpoint not configured (%s) - typed policy_failure '
                'upstream' % self._endpoint_env)
        questions = {
            'next_action': {
                'type': 'choice',
                'instructions': '%s %s' % (self._INSTRUCTIONS_TEMPLATE
                                           % question.context,
                                           question.prompt),
                'criteria': {
                    o.action: '%s — %s' % (o.criteria,
                                           self._CRITERIA_ENRICHMENT[o.action])
                    if o.action in self._CRITERIA_ENRICHMENT else o.criteria
                    for o in question.options
                },
            },
        }
        payload = {'model': self._model, 'state': state, 'questions': questions}
        rep = self._transport(self._endpoint, payload, self._timeout_s)
        # Response: {"answers": {"next_action": {choice, probabilities,
        # confidence}}, "usage": {...}}.  confidence is the CONCENTRATION of
        # the probability mass, not accuracy, so the routing signal is the
        # chosen option's own probability; confidence is kept as telemetry.
        answer = (rep.get('answers') or {}).get('next_action') or {}
        probabilities = answer.get('probabilities') or {}
        choice = str(answer.get('choice', '') or '')
        probability = float(probabilities.get(choice,
                                              answer.get('confidence', 0.0))
                            or 0.0)
        usage = rep.get('usage') or {}
        input_tokens = int(usage.get('input_tokens', usage.get('prompt_tokens', 0)) or 0)
        output_tokens = int(usage.get('output_tokens', usage.get('completion_tokens', 0)) or 0)
        tokens = int(usage.get('total_tokens', input_tokens + output_tokens) or 0)
        return JevResponse(
            choice=choice, probability=probability,
            raw={'backend': self.name, 'model': self._model,
                 'model_sha256': (None if self._injected else
                                  os.environ.get('FLEXCELL_JEV_MODEL_SHA256')),
                 'probabilities': probabilities,
                 'concentration': answer.get('confidence'),
                 'input_tokens': input_tokens, 'output_tokens': output_tokens,
                 'tokens': tokens})


def make_backend(spec):
    """Backend factory for the executor wiring (decision_policy=jev)."""
    if spec == 'typesafe':
        return TypeSafeBackend()
    if spec == 'local':
        return LocalReproductionBackend()
    if spec == 'clef':
        return ClefBackend()
    raise ValueError('unknown jev backend %r (typesafe|local|clef)' % (spec,))
