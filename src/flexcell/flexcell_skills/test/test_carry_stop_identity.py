"""A stop record must name what it stopped, and say who asked.

Measured before this change: 1432 `stop` events in carry.jsonl, 0 of which
named a session or an object, and 983 more stops than starts. A PICK could not
be traced through engage -> pin -> release because the identity was in memory
and was dropped at the write (carry_server.py:252).
"""
import threading
from types import SimpleNamespace
from unittest.mock import Mock

from flexcell_skills.carry_server import CarryServer

TOKEN = 'a1b2c3d4e5f60718293a4b5c6d7e8f90'


def node(session=TOKEN, object_id='target_box_a', backend='teleport',
         thread=None, guard_release=None):
    n = SimpleNamespace(_session=session, _object_id=object_id,
                        _offset=[0., 0., 0.], _backend=backend,
                        _thread=thread, _stop_evt=threading.Event(),
                        _retired_sessions=set(), _log=Mock(),
                        get_logger=Mock())
    n._publish_state = Mock()
    n._guard_release = Mock(return_value=True if guard_release is None
                            else guard_release)
    # the wrappers (_on_stop_topic / _on_release / _check_worker) reach the
    # real method through self, which a namespace cannot provide
    n._on_stop = lambda msg, **kw: CarryServer._on_stop(n, msg, **kw)
    return n


def stop_record(n, cause='unspecified'):
    assert CarryServer._on_stop(n, None, cause=cause) is True
    return n._log.write.call_args.args[0]


def test_stop_names_the_session_and_object_it_stopped():
    record = stop_record(node())
    assert record['event'] == 'stop'
    assert record['session'] == TOKEN
    assert record['object'] == 'target_box_a'
    assert record['engaged'] is True


def test_stop_names_the_caller():
    for cause in ('release', 'replace', 'worker_ended', 'shutdown', 'topic'):
        assert stop_record(node(), cause=cause)['cause'] == cause


def test_the_stop_topic_is_its_own_caller():
    n = node()
    assert CarryServer._on_stop_topic(n, None) is None
    assert n._log.write.call_args.args[0]['cause'] == 'topic'


def test_release_service_records_the_release_cause():
    n = node()
    assert CarryServer._on_release(n, None, SimpleNamespace()).success
    assert n._log.write.call_args.args[0]['cause'] == 'release'


def test_an_idle_stop_says_it_released_nothing():
    record = stop_record(node(session='', object_id=''))
    assert record['engaged'] is False
    assert record['session'] == ''
    assert record['object'] == ''


def test_identity_is_captured_before_the_state_is_cleared():
    """The record must not read back the attributes the same call just emptied."""
    n = node()
    CarryServer._on_stop(n, None, cause='release')
    assert (n._object_id, n._offset, n._session) == ('', None, '')
    record = n._log.write.call_args.args[0]
    assert (record['object'], record['session']) == ('target_box_a', TOKEN)


def test_session_stays_retired_after_a_recorded_stop():
    n = node()
    CarryServer._on_stop(n, None, cause='release')
    assert TOKEN in n._retired_sessions


def test_a_worker_that_will_not_join_still_blocks_the_stop():
    """Record keeping must not soften the safety outcome."""
    thread = Mock()
    thread.is_alive.return_value = True
    n = node(thread=thread)
    assert CarryServer._on_stop(n, None, cause='release') is False
    n._log.write.assert_not_called()
    assert n._offset == [0., 0., 0.]


def test_an_unconfirmed_physics_release_names_itself_too():
    n = node(backend='velocity_servo', guard_release=False)
    assert CarryServer._on_stop(n, None, cause='release') is False
    record = n._log.write.call_args.args[0]
    assert record['event'] == 'release_unconfirmed'
    assert record['session'] == TOKEN
    assert record['object'] == 'target_box_a'
    assert record['cause'] == 'release'


def test_worker_ended_records_the_session_it_was_serving():
    thread = Mock()
    thread.is_alive.return_value = False
    n = node(thread=thread)
    CarryServer._check_worker(n)
    first = n._log.write.call_args_list[0].args[0]
    assert first['event'] == 'worker_ended'
    assert first['session'] == TOKEN
    assert n._log.write.call_args_list[-1].args[0]['cause'] == 'worker_ended'
