from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import threading

import pytest


path = Path(__file__).resolve().parents[4] / 'setup/runtime_backend_metadata.py'
spec = importlib.util.spec_from_file_location('runtime_backend_metadata_test', path)
metadata = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metadata)


@contextmanager
def models_server(payload, status=200, chunked=False):
    requests = []
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.command, self.path, self.headers.get('Authorization')))
            self.send_response(status)
            if chunked:
                self.send_header('Transfer-Encoding', 'chunked')
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            pytest.fail('metadata collection must not invoke inference')

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield 'http://127.0.0.1:%s/v1/systemone' % server.server_port, requests, body
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def env(endpoint):
    return dict(FLEXCELL_JEV_ENDPOINT=endpoint, FLEXCELL_JEV_MODEL='clef',
                FLEXCELL_LLM_ENDPOINT=endpoint, FLEXCELL_LLM_MODEL='clef')


def test_live_context_and_exact_response_are_recorded(tmp_path, monkeypatch):
    # Loopback must work even with a broken global proxy, as inference does.
    monkeypatch.setenv('http_proxy', 'http://127.0.0.1:1')
    payload = b'{"data":[{"id":"clef","meta":{"n_ctx":16384}}],"created":123}\n'
    with models_server(payload) as (endpoint, requests, body):
        stable, receipt = metadata.snapshot_contexts('jev', tmp_path, env(endpoint))
    assert stable['fast'] == dict(status='OBSERVED', context_tokens=16384,
                                 model_id='clef', selection='requested_model',
                                 context_field='meta.n_ctx')
    assert stable['slow'] == dict(status='NOT_USED', context_tokens=None)
    assert requests == [('GET', '/v1/models', None)]
    assert (tmp_path / receipt['fast']['response_file']).read_bytes() == body
    assert receipt['fast']['response_sha256'] == hashlib.sha256(body).hexdigest()
    assert 'observed_at_utc' in receipt['fast']
    assert 'observed_at_utc' not in stable['fast']


def test_each_active_arm_has_its_own_context(tmp_path):
    with models_server({'data': [{'id': 'clef', 'meta': {'n_ctx': 16384}}]}) as fast:
        with models_server({'data': [{'id': 'clef', 'meta': {'n_ctx': 8192}}]}) as slow:
            config = env(fast[0])
            config['FLEXCELL_LLM_ENDPOINT'] = slow[0].replace('systemone', 'chat/completions')
            stable, receipt = metadata.snapshot_contexts('hybrid', tmp_path, config)
    assert stable['fast']['context_tokens'] == 16384
    assert stable['slow']['context_tokens'] == 8192
    assert set(receipt) == {'fast', 'slow'}
    assert len(fast[1]) == len(slow[1]) == 1


@pytest.mark.parametrize('policy', ['fsm', 'llm'])
def test_unused_and_authenticated_backends_make_no_requests(tmp_path, policy):
    with models_server({}) as (endpoint, requests, _):
        config = env(endpoint)
        config['FLEXCELL_LLM_API_KEY_FILE'] = str(tmp_path / 'must_not_read')
        stable, receipt = metadata.snapshot_contexts(policy, tmp_path, config)
    assert not requests and not receipt
    assert stable['fast']['status'] == 'NOT_USED'
    assert stable['slow']['status'] == ('NOT_USED' if policy == 'fsm'
                                      else 'NOT_QUERIED_AUTHENTICATED')
    assert stable['slow']['context_tokens'] is None


def test_typesafe_does_not_probe_vendor_metadata(tmp_path):
    stable, receipt = metadata.snapshot_contexts('jev', tmp_path, {}, fast_backend='typesafe')
    assert stable['fast']['status'] == 'NOT_QUERIED_AUTHENTICATED'
    assert not receipt


@pytest.mark.parametrize('value', [None, 0, -1, True, '16384', 16384.0])
def test_invalid_runtime_context_never_uses_a_default(value):
    payload = dict(data=[dict(id='clef', meta=dict(n_ctx=value, n_ctx_train=262144))])
    result = metadata._select_context(payload, 'clef')
    assert result['status'] == 'UNKNOWN' and result['context_tokens'] is None


def test_model_selection_does_not_pick_the_first_unrelated_model():
    models = [dict(id='other', meta=dict(n_ctx=8192)),
              dict(id='gguf', aliases=['clef'], meta=dict(n_ctx=16384))]
    result = metadata._select_context(dict(data=models), 'clef')
    assert result['model_id'] == 'gguf' and result['context_tokens'] == 16384
    assert metadata._select_context(dict(data=models), 'unknown')['context_tokens'] is None
    # A sole advertised GGUF is useful, but does not prove the request alias.
    sole = metadata._select_context(dict(data=models[:1]), 'clef')
    assert sole['selection'] == 'sole_advertised_model'
    duplicate = metadata._select_context(dict(data=[models[1], models[1]]), 'clef')
    assert duplicate['status'] == 'UNKNOWN'


@pytest.mark.parametrize('payload', [None, [], {}, {'data': []}, {'data': [None]},
                                    {'data': [{'meta': {'n_ctx': 16384}}]}])
def test_incomplete_metadata_cannot_claim_an_observed_context(payload):
    result = metadata._select_context(payload, 'clef')
    assert result['status'] == 'UNKNOWN' and result['context_tokens'] is None


@pytest.mark.parametrize('payload,status,expected', [
    (b'{invalid', 200, 'UNAVAILABLE'),
    (b'private server error text', 503, 'UNAVAILABLE'),
    (b'x' * (metadata.MAX_RESPONSE_BYTES + 1), 200, 'UNKNOWN'),
], ids=['invalid-json', 'unavailable', 'oversized'])
def test_failed_and_oversized_metadata_do_not_break_deployment(tmp_path, payload, status, expected):
    with models_server(payload, status) as (endpoint, _, _):
        stable, receipt = metadata.snapshot_contexts('jev', tmp_path, env(endpoint))
    assert stable['fast']['status'] == expected
    assert stable['fast']['context_tokens'] is None
    assert 'private server error text' not in json.dumps(receipt)


def test_connection_failure_preserves_unknown_context(tmp_path):
    with models_server({}) as (endpoint, _, _):
        pass
    stable, receipt = metadata.snapshot_contexts('jev', tmp_path, env(endpoint), timeout_s=.1)
    assert stable['fast'] == dict(status='UNAVAILABLE', context_tokens=None)
    assert receipt['fast']['error_type'] == 'URLError'


def test_truncated_http_body_does_not_interrupt_deployment(tmp_path):
    with models_server(b'10\r\n{', chunked=True) as (endpoint, _, _):
        stable, receipt = metadata.snapshot_contexts('jev', tmp_path, env(endpoint))
    assert stable['fast'] == dict(status='UNAVAILABLE', context_tokens=None)
    assert receipt['fast']['error_type'] == 'IncompleteRead'


@pytest.mark.parametrize('endpoint', [
    'http://user:secret@127.0.0.1/v1/systemone',
    'http://127.0.0.1/v1/systemone?key=secret',
    'file:///tmp/secret', 'http://127.0.0.1/not-an-inference-endpoint',
])
def test_unsupported_urls_are_not_requested_or_copied(tmp_path, endpoint):
    stable, receipt = metadata.snapshot_contexts('jev', tmp_path, env(endpoint))
    assert stable['fast']['status'] == 'UNKNOWN'
    assert receipt['fast'] == {}
    assert not list(tmp_path.iterdir())


def test_ephemeral_response_fields_do_not_change_context_identity(tmp_path):
    identities, receipts = [], []
    for created in (100, 200):
        with models_server(dict(data=[dict(id='clef', meta=dict(n_ctx=16384))],
                                created=created)) as (endpoint, _, _):
            identity, receipt = metadata.snapshot_contexts('jev', tmp_path, env(endpoint))
            identities.append(identity)
            receipts.append(receipt)
    assert identities[0] == identities[1]
    assert receipts[0]['fast']['response_sha256'] != receipts[1]['fast']['response_sha256']
