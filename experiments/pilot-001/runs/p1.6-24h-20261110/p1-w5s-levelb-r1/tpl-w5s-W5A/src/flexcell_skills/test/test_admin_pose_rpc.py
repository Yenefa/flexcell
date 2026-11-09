"""Bound retries to stalled transport; service rejection/crash never qualifies."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pytest


@pytest.fixture
def admin(monkeypatch):
    path = Path(__file__).resolve().parents[4] / 'setup/flexcell_admin.py'
    spec = importlib.util.spec_from_file_location('admin_pose_rpc_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    transport = ModuleType('gz.transport13')
    transport.Node = lambda: SimpleNamespace(request=lambda *args: (True, SimpleNamespace(data=False)))
    monkeypatch.setitem(sys.modules, 'gz.transport13', transport)
    return module


def reply(transport_ok, response_data, rc=0):
    return subprocess.CompletedProcess([], rc, json.dumps(dict(
        transport_ok=transport_ok, response_data=response_data)), '')


def calls_with(monkeypatch, admin, results):
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        result = results[min(len(calls)-1, len(results)-1)]
        if isinstance(result, Exception):
            raise result
        return result
    monkeypatch.setattr(admin.subprocess, 'run', run)
    return calls


def test_stalled_transport_retries_in_fresh_process(monkeypatch, admin):
    calls = calls_with(monkeypatch, admin, [reply(False, False), reply(True, True)])
    ok, details = admin.gz_set_pose('target_box_a', (.22, 0., .0175))
    assert ok is True and len(calls) == 2
    assert all('flexcell_skills.pose_request_worker' in args for args in calls)
    assert len(details['attempts']) == 2
    assert details['attempts'][0]['transport_ok'] is False


def test_retry_budget_is_bounded(monkeypatch, admin):
    calls = calls_with(monkeypatch, admin, [reply(False, False)])
    ok, details = admin.gz_set_pose('target_box_a', (.22, 0., .0175))
    assert ok is False and len(calls) == 3 and len(details['attempts']) == 3


@pytest.mark.parametrize('result', [
    reply(True, False),  # A delivered request with Boolean.data=false.
    reply(True, True, -6),  # Printed success before a native abort.
    subprocess.CompletedProcess([], 0, '{"transport_ok":true}', ''),
    subprocess.CompletedProcess([], 0, 'not JSON', ''),
    subprocess.TimeoutExpired('pose-worker', 5),
])
def test_rejection_or_invalid_exit_is_not_retried(monkeypatch, admin, result):
    calls = calls_with(monkeypatch, admin, [result, reply(True, True)])
    ok, details = admin.gz_set_pose('target_box_a', (.22, 0., .0175))
    assert ok is False and len(calls) == 1
    assert len(details['attempts']) == 1
