"""Read runtime context metadata without performing inference or reading API keys.

Only llama.cpp's live ``meta.n_ctx`` is a context observation. Training limits,
request token caps and profile defaults are not substitutes for that value.
"""
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request


MAX_RESPONSE_BYTES = 65536


def _models_url(endpoint):
    parsed = urllib.parse.urlsplit(endpoint)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError('metadata requires an HTTP endpoint without credentials or query')
    for suffix in ('/chat/completions', '/completions', '/systemone'):
        if parsed.path.endswith(suffix):
            path = parsed.path[:-len(suffix)] + '/models'
            return urllib.parse.urlunsplit(parsed._replace(path=path))
    raise ValueError('unsupported inference endpoint path')


def _select_context(payload, requested_model):
    if not isinstance(payload, dict) or not isinstance(payload.get('data'), list):
        return dict(status='UNKNOWN', reason='invalid_models_response', context_tokens=None)
    models = [model for model in payload['data'] if isinstance(model, dict)]
    matches = [model for model in models if model.get('id') == requested_model
               or (isinstance(model.get('aliases'), list)
                   and requested_model in model['aliases'])]
    if len(matches) == 1:
        selected, selection = matches[0], 'requested_model'
    elif not matches and len(payload['data']) == 1 and len(models) == 1:
        # llama-server may ignore the request alias and advertise the GGUF path.
        # Record that weaker association explicitly; it does not verify weights.
        selected, selection = models[0], 'sole_advertised_model'
    else:
        return dict(status='UNKNOWN', reason='ambiguous_or_missing_model', context_tokens=None)
    model_id = selected.get('id')
    if not isinstance(model_id, str) or not model_id:
        return dict(status='UNKNOWN', reason='missing_model_id', context_tokens=None)
    meta = selected.get('meta')
    context = meta.get('n_ctx') if isinstance(meta, dict) else None
    identity = dict(model_id=model_id, selection=selection, context_field='meta.n_ctx')
    if type(context) is not int or context <= 0:
        return dict(identity, status='UNKNOWN', reason='missing_or_invalid_runtime_context',
                    context_tokens=None)
    return dict(identity, status='OBSERVED', context_tokens=context)


def _observe(endpoint, model, destination, timeout_s):
    try:
        url = _models_url(endpoint)
    except ValueError:
        return (dict(status='UNKNOWN', reason='unsupported_endpoint', context_tokens=None), {})
    evidence = dict(url=url, observed_at_utc=datetime.now(timezone.utc).isoformat())
    request = urllib.request.Request(url, headers={'Accept': 'application/json'})
    # Match the inference clients' direct loopback transport (including SSH forwards).
    opener = (urllib.request.build_opener(urllib.request.ProxyHandler({}))
              if urllib.parse.urlsplit(url).hostname in ('localhost', '127.0.0.1', '::1')
              else urllib.request.build_opener())
    try:
        with opener.open(request, timeout=timeout_s) as reply:
            raw = reply.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            return (dict(status='UNKNOWN', reason='metadata_response_too_large',
                         context_tokens=None), evidence)
        destination.write_bytes(raw)
        evidence.update(response_file=destination.name,
                        response_sha256=hashlib.sha256(raw).hexdigest())
        observation = _select_context(json.loads(raw), model)
    except (OSError, urllib.error.URLError, ValueError, http.client.HTTPException) as error:
        # Do not persist server error bodies, URLs from exceptions, or credentials.
        evidence['error_type'] = type(error).__name__
        observation = dict(status='UNAVAILABLE', context_tokens=None)
    return observation, evidence


def snapshot_contexts(policy, directory, env=None, timeout_s=2.0, fast_backend='local'):
    """Return stable fingerprint fields and separate byte-preserving observations.

    Inactive arms make no requests. Authenticated services remain UNKNOWN without
    reading their key files. Each used unauthenticated arm gets one bounded GET.
    The response hashes and observation times are receipts, not fingerprint fields.
    """
    if policy not in ('fsm', 'jev', 'llm', 'hybrid'):
        raise ValueError('unsupported policy')
    directory = Path(directory)
    env = os.environ if env is None else env
    stable, evidence = {}, {}
    for arm, name, used in (('fast', 'JEV', policy in ('jev', 'hybrid')),
                            ('slow', 'LLM', policy in ('llm', 'hybrid'))):
        if not used:
            stable[arm] = dict(status='NOT_USED', context_tokens=None)
            continue
        if env.get('FLEXCELL_%s_API_KEY_FILE' % name) or (
                name == 'JEV' and fast_backend == 'typesafe'):
            stable[arm] = dict(status='NOT_QUERIED_AUTHENTICATED', context_tokens=None)
            continue
        stable[arm], evidence[arm] = _observe(
            env.get('FLEXCELL_%s_ENDPOINT' % name, ''),
            env.get('FLEXCELL_%s_MODEL' % name, ''),
            directory / ('%s_models.json' % arm), timeout_s)
    return stable, evidence
