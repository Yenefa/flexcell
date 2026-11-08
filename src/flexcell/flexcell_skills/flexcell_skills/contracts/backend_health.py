"""Deployment-scoped Clef startup probe, independent of frozen prompt bytes."""

import math
import os
import socket
from urllib.parse import urlparse


def startup_health(backend, spec, environment=None, connect=None):
    """Keep the backend default unless this deployment explicitly opts in.

    This checks TCP reachability, not inference or routing eligibility. The
    deadline cannot exceed the configured inference timeout. No retry is hidden.
    """
    env = os.environ if environment is None else environment
    setting = env.get('FLEXCELL_JEV_HEALTH_TIMEOUT_S')
    if spec != 'clef' or setting is None or getattr(backend, '_injected', False):
        return backend.health()
    try:
        timeout = float(setting)
        inference_timeout = float(env.get('FLEXCELL_JEV_TIMEOUT_S', '2'))
        if not all(math.isfinite(value) and value > 0 for value in (timeout, inference_timeout)):
            raise ValueError('timeouts must be finite and positive')
        timeout = min(timeout, inference_timeout)
        endpoint = urlparse(env.get('FLEXCELL_JEV_ENDPOINT', ''))
        if endpoint.scheme not in ('http', 'https') or not endpoint.hostname:
            raise ValueError('invalid HTTP endpoint')
        port = endpoint.port or (443 if endpoint.scheme == 'https' else 80)
    except (TypeError, ValueError) as exc:
        return False, 'invalid startup health configuration: %s' % exc
    try:
        with (connect or socket.create_connection)((endpoint.hostname, port), timeout=timeout):
            pass
    except OSError as exc:
        return False, 'TCP startup probe unavailable: %s (deadline %.3fs)' % (type(exc).__name__, timeout)
    return True, 'TCP startup reachable (deadline %.3fs; typed inference checked on decision)' % timeout
