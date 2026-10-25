"""Real loop bodies, scripted TF/transport and virtual time; no ROS or robot.

Compare external control calls with the pinned pre-observation loop. Extra
clock reads have no cost in the differential cases; a separate test makes
the possible logging overhead explicit. This is not a wall-time equivalence
or a physical acceptance test.
"""
import ast
from copy import deepcopy
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[4]
REFERENCE = ROOT / 'setup/acceptance/carry_observation_20261025/loop_before.txt'
SERVER = ROOT / 'src/flexcell/flexcell_skills/flexcell_skills/carry_server.py'
REFERENCE_SHA = 'c16814b9662cf417e9be8dbe1018b126d9ec8ea4eedf2df06fdd4f4c2b36e664'
OBJECT, SESSION = 'target_box_a', 'a' * 32


class Clock:
    def __init__(self):
        self.now = 10_000_000_000

    def monotonic_ns(self):
        return self.now


def loop_body(path, clock):
    source = path.read_bytes()
    if path == REFERENCE:
        assert hashlib.sha256(source).hexdigest() == REFERENCE_SHA
    tree = ast.parse(source)
    node = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == '_loop')
    namespace = {'time': clock}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['_loop']


class Rig:
    def __init__(self, lookups, replies=(), backend='teleport', offset=True,
                 broken_summary=False, summary_cost_ns=0, pose_error=False,
                 broken_error_logger=False):
        self.lookups, self.replies = list(lookups), list(replies)
        self.clock = Clock()
        self.trace, self.records, self.errors = [], [], []
        self.index = self.requests = self.summary_attempts = 0
        self.stopped = not self.lookups
        self.broken_summary, self.summary_cost_ns = broken_summary, summary_cost_ns
        self.broken_error_logger = broken_error_logger
        self.pose_error = pose_error
        self._backend, self._period, self._service = backend, .1, 'pin-service'
        self._Pose, self._Boolean = 'pose-type', 'bool-type'
        # Summaries must use worker arguments, not mutable global ownership.
        self._object_id, self._session = 'replacement-object', 'replacement-session'
        self.offset = [0., 0., -.15] if offset else None
        self._gz_node = SimpleNamespace(request=self.request)
        self._log = SimpleNamespace(write=self.write)

    def is_set(self):
        return self.stopped

    def set(self):
        self.trace.append(('set',))
        self.stopped = True

    def wait(self, period):
        self.trace.append(('wait', period))
        self.clock.now += int(period * 1e9)
        self.stopped |= self.index >= len(self.lookups)

    def _ee(self):
        mode = self.lookups[self.index]
        self.index += 1
        self.trace.append(('lookup', mode))
        self.clock.now += 500_000_000 if mode == 'missing' else 1_000_000
        if mode == 'raise':
            raise RuntimeError('unexpected lookup error')
        return None if mode == 'missing' else [1., 2., 3.]

    def _pose(self, object_id, offset, ee, session):
        self.trace.append(('pose', object_id, tuple(offset), tuple(ee), session))
        if self.pose_error:
            raise ValueError('pose construction failed')
        x, y, z = [ee[i] + offset[i] for i in range(3)]
        return SimpleNamespace(name=object_id, position=SimpleNamespace(x=x, y=y, z=z))

    def request(self, service, req, pose_type, bool_type, timeout):
        self.trace.append(('request', service, req.name,
                           (req.position.x, req.position.y, req.position.z),
                           pose_type, bool_type, timeout))
        self.clock.now += 5_000_000
        mode = self.replies[min(self.requests, len(self.replies) - 1)] if self.replies else 'ok'
        self.requests += 1
        if mode == 'error':
            raise RuntimeError('transport failure')
        return mode == 'ok'

    def _request_ok(self, response):
        self.trace.append(('interpret', response))
        return response

    def get_logger(self):
        return self

    def warn(self, message):
        self.trace.append(('warn', message))

    def error(self, message):
        if self.broken_error_logger:
            raise RuntimeError('synthetic logger shutdown')
        self.errors.append(message)

    def write(self, record):
        if record['event'] == 'teleport_loop_summary':
            self.summary_attempts += 1
            self.clock.now += self.summary_cost_ns
            if self.broken_summary:
                raise OSError('synthetic observation write failure')
        self.records.append(deepcopy(record))


def run(path=SERVER, **kwargs):
    rig = Rig(**kwargs)
    error = None
    try:
        loop_body(path, rig.clock)(rig, OBJECT, rig.offset, rig, SESSION)
    except Exception as exc:
        error = (type(exc).__name__, str(exc))
    return rig, error


def observations(rig):
    return [r for r in rig.records if r['event'] == 'teleport_loop_summary']


CASES = [
    dict(lookups=[]),
    dict(lookups=['missing']),
    dict(lookups=['missing'] * 8),
    dict(lookups=['ready'] * 25),
    dict(lookups=['missing', 'ready', 'missing', 'ready'], replies=['rejected', 'ok']),
    dict(lookups=['ready'] * 25, replies=['rejected']),
    dict(lookups=['ready'] * 25, replies=['error']),
    dict(lookups=['ready'] * 6, replies=['error', 'rejected', 'ok']),
    dict(lookups=['ready', 'missing', 'ready'], offset=False),
    dict(lookups=['ready'] * 7, replies=['rejected'], backend='velocity_servo'),
    dict(lookups=['ready', 'missing', 'ready', 'missing', 'ready'],
         replies=['error'], backend='velocity_servo'),
    dict(lookups=['ready'] * 4, backend='velocity_servo'),
    dict(lookups=['raise']),
    dict(lookups=['ready'], pose_error=True),
    dict(lookups=['missing'] * 8, broken_summary=True),
    dict(lookups=['ready'] * 25, broken_summary=True, broken_error_logger=True),
]


@pytest.mark.parametrize('case', CASES)
def test_control_calls_and_legacy_records_match_pinned_loop(case):
    before, before_error = run(REFERENCE, **case)
    after, after_error = run(SERVER, **case)
    assert after_error == before_error
    assert after.trace == before.trace
    assert after.requests == before.requests
    assert after.stopped == before.stopped
    assert [r for r in after.records if r['event'] != 'teleport_loop_summary'] == before.records
    if case.get('backend') == 'velocity_servo':
        assert not observations(after)


def test_missing_tf_is_counted_without_sending_a_pin():
    rig, error = run(lookups=['missing'] * 5)
    assert error is None and rig.requests == 0
    final = observations(rig)[-1]
    assert final['final'] is True
    assert (final['ee_lookup_count'], final['ee_missing_count']) == (5, 5)
    assert final['ee_lookup_ns_total'] == 2_500_000_000
    assert final['ee_lookup_ns_max'] == 500_000_000
    assert final['ee_missing_streak_max'] == 5
    assert final['pin_requests'] == final['pin_failed'] == final['pin_confirmed'] == 0


def test_gaps_and_pin_failures_have_separate_denominators():
    rig, error = run(lookups=['missing', 'missing', 'ready', 'missing', 'ready', 'ready'],
                     replies=['error', 'rejected', 'ok'])
    assert error is None
    final = observations(rig)[-1]
    assert final['ee_lookup_count'] == 6 and final['ee_missing_count'] == 3
    assert final['ee_missing_streak_max'] == 2 and final['ee_missing_streak'] == 0
    assert (final['pin_requests'], final['pin_confirmed'], final['pin_failed']) == (3, 1, 2)


def test_missing_offset_is_not_a_pin_or_a_missing_lookup():
    rig, _ = run(lookups=['ready', 'ready'], offset=False)
    final = observations(rig)[-1]
    assert final['ee_missing_count'] == final['pin_requests'] == 0
    assert final['pin_skipped_no_offset'] == 2


def test_summaries_are_bounded_and_keep_worker_identity():
    rig, _ = run(lookups=['missing'] * 20)
    rows = observations(rig)
    periodic = [r for r in rows if not r['final']]
    stamps = [rows[0]['started_mono_ns']] + [r['sample_mono_ns'] for r in periodic]
    assert all(b - a >= 1_000_000_000 for a, b in zip(stamps, stamps[1:]))
    assert len([r for r in rows if r['final']]) == 1
    assert all((r['session'], r['object'], r['backend']) == (SESSION, OBJECT, 'teleport')
               for r in rows)
    assert periodic[0]['ee_lookup_count'] < rows[-1]['ee_lookup_count']


def test_final_summary_is_emitted_after_a_worker_exception():
    rig, error = run(lookups=['ready'], pose_error=True)
    assert error == ('ValueError', 'pose construction failed')
    assert len(observations(rig)) == 1
    assert observations(rig)[0]['final'] is True


@pytest.mark.parametrize('broken_logger', [False, True])
def test_observation_failure_does_not_abort_pinning(broken_logger):
    rig, error = run(lookups=['ready'] * 25, broken_summary=True,
                     broken_error_logger=broken_logger)
    assert error is None and rig.requests == 25
    assert rig.summary_attempts > 0
    assert rig.errors or broken_logger


def test_summary_io_can_extend_elapsed_time():
    before, _ = run(REFERENCE, lookups=['ready'])
    after, _ = run(SERVER, lookups=['ready'], summary_cost_ns=2_000_000)
    assert after.trace == before.trace
    assert after.clock.now - before.clock.now == 2_000_000
    assert observations(after)[0]['ee_lookup_ns_total'] == 1_000_000


def test_replaced_sessions_do_not_share_counters():
    first, _ = run(lookups=['missing', 'missing'])
    second, _ = run(lookups=['ready'])
    assert observations(first)[-1]['ee_missing_count'] == 2
    assert observations(second)[-1]['ee_missing_count'] == 0
    assert observations(second)[-1]['ee_lookup_count'] == 1
