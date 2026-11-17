"""One TLS hiccup must not end a batch; a timeout still must.

MEASURED 2026-11-17: two full batches stopped at slots 5 and 7 with
URLError("UNEXPECTED_EOF_WHILE_READING"). The handshake died before the request
was written, so no model answer existed to charge for, and retrying costs
nothing. A timeout is different: the request may have been processed, so it is
not retried and still surfaces as the unconfirmed terminal the protocol wants.
"""
import ssl
import sys
from pathlib import Path
from urllib.error import URLError

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import llm_transport as L  # noqa: E402


class _Client:
    def __init__(self, failures):
        self.failures = list(failures)
        self.calls = 0

    def chat(self, messages):
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        return {"content": "ok", "tokens": 7, "model": "m", "seconds": 0.1}


def _transport(failures):
    transport = L.GatedTransport.__new__(L.GatedTransport)
    transport.client = _Client(failures)
    transport.calls = 0
    transport.total_tokens = 0
    return transport


def test_a_dropped_handshake_is_retried_and_reported(monkeypatch):
    monkeypatch.setattr(L.time, "sleep", lambda _s: None)
    transport = _transport([URLError(ssl.SSLError("UNEXPECTED_EOF_WHILE_READING")),
                            URLError(ssl.SSLError("UNEXPECTED_EOF_WHILE_READING"))])
    reply = transport.chat([{"role": "user", "content": "hi"}])
    assert reply["text"] == "ok"
    assert reply["connection_retries"] == 2
    assert transport.client.calls == 3
    assert transport.calls == 1, "the retries are one interaction, not three"


def test_a_timeout_is_not_retried(monkeypatch):
    monkeypatch.setattr(L.time, "sleep", lambda _s: None)
    transport = _transport([TimeoutError("read timed out")])
    try:
        transport.chat([{"role": "user", "content": "hi"}])
    except TimeoutError:
        pass
    else:
        raise AssertionError("a timeout was swallowed")
    assert transport.client.calls == 1, "a retried timeout could double-charge"


def test_a_refused_connection_is_not_treated_as_a_model_answer(monkeypatch):
    monkeypatch.setattr(L.time, "sleep", lambda _s: None)
    transport = _transport([URLError(ConnectionRefusedError("refused"))] * 3)
    try:
        transport.chat([{"role": "user", "content": "hi"}])
    except URLError:
        pass
    else:
        raise AssertionError("three refusals were reported as a reply")
    assert transport.calls == 0
