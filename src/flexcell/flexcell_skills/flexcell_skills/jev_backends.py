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
import urllib.error
import urllib.request

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
                 model_env='FLEXCELL_JEV_MODEL'):
        self._injected = transport is not None
        self._endpoint = os.environ.get(endpoint_env, '')
        self._model = model or os.environ.get(model_env, 'local-jev')
        self._transport = transport or self._http_transport

    @staticmethod
    def _http_transport(url, payload, timeout_s):
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return json.loads(resp.read().decode())

    def health(self):
        if not self._endpoint:
            return False, ('FLEXCELL_JEV_ENDPOINT not set - local '
                           'reproduction server unavailable')
        return True, self._endpoint

    def _render(self, state, question):
        """Fixed prompt template: canonical JSON embedded verbatim + the
        numbered Choice menu + the response contract (structured output)."""
        menu = '\n'.join(
            '%d. %s — %s' % (i, o.action, o.criteria)
            for i, o in enumerate(question.options, 1))
        actions = ', '.join(o.action for o in question.options)
        return (
            'You are the task-level decision policy of a robotic workcell.\n'
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
            'max_tokens': 32,
            'temperature': 0.0,
        }
        rep = self._transport(self._endpoint, payload, 10.0)
        text = (rep.get('choices') or [{}])[0].get('text', '')
        parsed = json.loads(text)
        return JevResponse(
            choice=str(parsed.get('choice', '')),
            probability=float(parsed.get('confidence', 0.0)),
            raw={'backend': self.name,
                 'tokens': int(rep.get('usage', {}).get('total_tokens', 0) or 0)})


def make_backend(spec):
    """Backend factory for the executor wiring (decision_policy=jev)."""
    if spec == 'typesafe':
        return TypeSafeBackend()
    if spec == 'local':
        return LocalReproductionBackend()
    raise ValueError('unknown jev backend %r (typesafe|local)' % (spec,))
