"""A deployment deadline must not alter prompt identity or hide probe failures."""

from contextlib import nullcontext
from unittest.mock import Mock

import pytest

from flexcell_skills.contracts.backend_health import startup_health


ENV = dict(FLEXCELL_JEV_ENDPOINT='http://100.87.190.44:11435/v1/systemone',
           FLEXCELL_JEV_TIMEOUT_S='45', FLEXCELL_JEV_HEALTH_TIMEOUT_S='10')


def backend(injected=False):
    return Mock(_injected=injected, health=Mock(return_value=(False, 'original two-second probe')))


def test_missing_opt_in_and_other_backends_keep_original_health():
    for spec, env in (('clef', {}), ('local', ENV), ('typesafe', ENV)):
        value = backend()
        connect = Mock()
        assert startup_health(value, spec, env, connect) == (False, 'original two-second probe')
        value.health.assert_called_once()
        connect.assert_not_called()


def test_explicit_deadline_uses_direct_tcp_and_never_changes_backend():
    value = backend()
    connect = Mock(return_value=nullcontext())
    ok, detail = startup_health(value, 'clef', ENV, connect)
    assert ok and '10.000s' in detail and 'typed inference checked on decision' in detail
    connect.assert_called_once_with(('100.87.190.44', 11435), timeout=10.)
    value.health.assert_not_called()


def test_health_deadline_cannot_exceed_inference_budget():
    connect = Mock(return_value=nullcontext())
    assert startup_health(backend(), 'clef', dict(ENV, FLEXCELL_JEV_TIMEOUT_S='3'), connect)[0]
    assert connect.call_args.kwargs['timeout'] == 3.


@pytest.mark.parametrize('setting', ['0', '-1', 'nan', 'inf', '', 'invalid'])
def test_invalid_deadline_fails_closed(setting):
    connect = Mock()
    ok, detail = startup_health(backend(), 'clef', dict(ENV, FLEXCELL_JEV_HEALTH_TIMEOUT_S=setting), connect)
    assert not ok and 'invalid startup health configuration' in detail
    connect.assert_not_called()


def test_network_failure_is_retained_without_retry():
    connect = Mock(side_effect=TimeoutError())
    ok, detail = startup_health(backend(), 'clef', ENV, connect)
    assert not ok and 'TimeoutError' in detail and '10.000s' in detail
    connect.assert_called_once()


def test_injected_backend_never_probes_network():
    connect = Mock()
    value = backend(injected=True)
    assert startup_health(value, 'clef', ENV, connect) == value.health.return_value
    connect.assert_not_called()


def test_invalid_endpoint_is_not_reported_reachable():
    for endpoint in ('', 'file:///tmp/socket', 'http://host:invalid'):
        connect = Mock()
        assert not startup_health(backend(), 'clef', dict(ENV, FLEXCELL_JEV_ENDPOINT=endpoint), connect)[0]
        connect.assert_not_called()
