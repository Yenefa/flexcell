"""Deterministic failure-injection lifecycle (T6 hardening, 4 states).

The 2026-09-29 benchmark found the injection channel was *fire-and-forget*:
`94_scenario_runner.py` published a request on a topic and never learned
whether the pick server had taken it.  Two consequences, both measured:

- a request that was never delivered silently left the cell running under the
  wrong condition (one S5 episode of 20 SUCCEEDED although exhaustion was
  expected, because its `always` injection never armed - the client's
  "INJECT WARNING: no subscriber matched" was swallowed by the runner);
- conversely a request that WAS delivered was never cleared, so every later
  episode in the batch inherited it (S7 0/10, pre-failed by the leftover
  `exhaust_demo_v1:always`).

So the injection is now an explicit four-state lifecycle, and the requester can
*seal* each step by waiting for the matching transition:

    requested -> armed -> applied
    any state -> cleared        (the empty payload is the clear signal)

- `requested`  a request arrived and was understood (bad payloads stop here)
- `armed`      validated and will affect the next matching pick
- `applied`    a pick attempt was actually failed by the injection
- `cleared`    disarmed; no later pick is affected

Pure python (no rclpy) so the transitions are unit-testable, and the server
only has to publish snapshots.  Request payload grammar stays backward
compatible: `scenario[:mode]`, with an optional `#request_id` suffix so a
requester can correlate its own request with the transition it observes.
"""

# The empty payload is the clear signal understood by the historical server.
CLEAR_PAYLOAD = ''

IDLE = 'idle'
REQUESTED = 'requested'
ARMED = 'armed'
APPLIED = 'applied'
CLEARED = 'cleared'

STATES = (IDLE, REQUESTED, ARMED, APPLIED, CLEARED)
#: states in which an injection can still fail a pick attempt
LIVE_STATES = (ARMED, APPLIED)
VALID_MODES = ('once', 'always')


def parse_request(payload):
    """Parse a request payload.

    Returns ``(scenario, mode, request_id)`` for a real request, or
    ``('', '', request_id)`` for the clear signal.  Raises ``ValueError`` for a
    malformed request (bad mode) so the caller can keep it in `requested` and
    refuse to arm rather than guessing.

    A clear may carry a request id as a bare ``#id`` (the empty payload cannot
    hold a suffix), so a requester can correlate the `cleared` transition with
    its own request exactly as it does for an arm.
    """
    text = (payload or '').strip()
    if text.startswith('#'):
        # clear with a correlation id: "#r42" (or just "#")
        return ('', '', text[1:].strip())
    if not text:
        return ('', '', '')
    request_id = ''
    if '#' in text:
        text, _, request_id = text.partition('#')
        text = text.strip()
    if ':' in text:
        scenario, _, mode = text.partition(':')
        scenario, mode = scenario.strip(), mode.strip()
    else:
        scenario, mode = text, 'once'
    if not scenario:
        raise ValueError('empty scenario in payload %r' % (payload,))
    if mode not in VALID_MODES:
        raise ValueError('bad mode %r (payload=%r)' % (mode, payload))
    return (scenario, mode, request_id)


class InjectionLifecycle:
    """Tracks one injection arm/clear/apply sequence, deterministically."""

    def __init__(self):
        self.reset_to_idle()

    def reset_to_idle(self):
        self.state = IDLE
        self.scenario = ''
        self.mode = ''
        self.request_id = ''
        self.applied_count = 0
        self.error = ''
        self._attempts = {}

    # ------------------------------------------------------------- requests
    def on_request(self, payload):
        """Handle a raw request payload. Returns the new state."""
        try:
            scenario, mode, request_id = parse_request(payload)
        except ValueError as exc:
            # understood as a request, refused as an arming: stay `requested`
            # and record why. Never silently ignore it.
            self.state = REQUESTED
            self.scenario = ''
            self.mode = ''
            self.error = str(exc)
            return self.state
        self.error = ''
        self.request_id = request_id
        if not scenario:
            # clear
            self.state = CLEARED
            self.scenario = ''
            self.mode = ''
            self.applied_count = 0
            self._attempts = {}
            return self.state
        self.state = REQUESTED
        self.scenario = scenario
        self.mode = mode
        self.applied_count = 0
        self._attempts = {}
        self.state = ARMED
        return self.state

    # ------------------------------------------------------------- per-pick
    def on_pick_attempt(self, object_name):
        """Decide whether this pick attempt must fail.

        Returns a detail string when the attempt is to be failed, else None.
        The per-(scenario, object) counter is what makes `once` mean "the first
        attempt of this object only", exactly as the frozen Week-1.5 semantics.
        """
        if self.state not in LIVE_STATES or not self.scenario:
            return None
        key = '%s|%s' % (self.scenario, object_name)
        attempt = self._attempts.get(key, 0) + 1
        self._attempts[key] = attempt
        if self.mode == 'once' and attempt > 1:
            return None
        self.state = APPLIED
        self.applied_count += 1
        return ('injected failure (scenario=%s mode=%s attempt=%d)'
                % (self.scenario, self.mode, attempt))

    # -------------------------------------------------------------- snapshot
    def snapshot(self):
        """JSON-ready view for the status topic / episode records."""
        return {
            'state': self.state,
            'scenario': self.scenario,
            'mode': self.mode,
            'request_id': self.request_id,
            'applied_count': self.applied_count,
            'error': self.error,
            'live': self.state in LIVE_STATES,
        }
