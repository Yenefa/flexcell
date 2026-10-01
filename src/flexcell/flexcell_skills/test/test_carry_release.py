"""Release acknowledgement must wait for pinning to finish, or report failure."""
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

from flexcell_skills.carry_server import CarryServer


def backend(thread, event):
    node = SimpleNamespace(_thread=thread, _stop_evt=event, _offset=[0, 0, 0],
                           _object_id='a', _log=Mock(), get_logger=Mock())
    node._publish_state = Mock()
    node._on_stop = lambda msg: CarryServer._on_stop(node, msg)
    return node


def test_release_ack_waits_for_inflight_pin_and_is_idempotent():
    stop = threading.Event()
    finished = threading.Event()

    def pinning():
        stop.wait()
        time.sleep(.05)
        finished.set()

    thread = threading.Thread(target=pinning)
    thread.start()
    node = backend(thread, stop)
    response = CarryServer._on_release(node, None, SimpleNamespace())
    assert response.success and finished.is_set() and not thread.is_alive()
    assert node._offset is None
    assert CarryServer._on_release(node, None, SimpleNamespace()).success


def test_release_ack_fails_when_servo_thread_does_not_join():
    thread = Mock()
    thread.is_alive.return_value = True
    node = backend(thread, threading.Event())
    response = CarryServer._on_release(node, None, SimpleNamespace())
    assert response.success is False
    assert node._offset is not None


def test_velocity_release_is_not_published_off_without_physics_confirmation():
    node = backend(None, threading.Event())
    node._backend = 'velocity_servo'
    node._guard_release = Mock(return_value=False)
    response = CarryServer._on_release(node, None, SimpleNamespace())
    assert not response.success and node._offset is not None
    node._publish_state.assert_not_called()


def test_velocity_release_confirms_physics_before_publishing_off():
    node = backend(None, threading.Event())
    node._backend = 'velocity_servo'
    node._guard_release = Mock(return_value=True)
    response = CarryServer._on_release(node, None, SimpleNamespace())
    assert response.success and node._offset is None
    node._guard_release.assert_called_once_with('')
    node._publish_state.assert_called_once()


def test_transport_timeout_cannot_be_hidden_by_boolean_reply():
    assert not CarryServer._request_ok((False, SimpleNamespace(data=True)))
    assert not CarryServer._request_ok((True, SimpleNamespace(data=False)))
    assert CarryServer._request_ok((True, SimpleNamespace(data=True)))


def test_duplicate_engage_reuses_owner_and_old_engage_cannot_release_new_owner():
    token = 'a' * 32
    node = SimpleNamespace(_base='world', _session=token, _offset=[0., 0., 0.],
                           _object_id='a', _thread=Mock(), _retired_sessions=set(),
                           _engage=Mock())
    node._thread.is_alive.return_value = True
    req = SimpleNamespace(request_id=token, object_id='a', reference_frame='world',
                          offset=[0., 0., 0.])
    assert CarryServer._on_engage(node, req, SimpleNamespace()).success
    node._engage.assert_not_called()
    node._retired_sessions.add(token)
    node._session = 'b' * 32
    assert not CarryServer._on_engage(node, req, SimpleNamespace()).success
    node._engage.assert_not_called()


def test_lost_engage_response_retries_same_request_identity(monkeypatch):
    from flexcell_skills import pick_server
    first, second = Mock(), Mock()
    client = Mock()
    client.wait_for_service.return_value = True
    client.call_async.side_effect = [first, second]
    waits = iter(['timeout', 'done'])
    monkeypatch.setattr(pick_server, 'wait_future', lambda future, seconds: next(waits))
    def result():
        token = client.call_async.call_args.args[0].request_id
        return SimpleNamespace(success=True, session=token, message='confirmed')
    second.result.side_effect = result
    node = SimpleNamespace(_base='world', _carry_engage=client)
    assert pick_server.PickServer._engage_carry(node, 'a', [0., 0., 0.])[0]
    assert client.call_async.call_args_list[0].args[0] is client.call_async.call_args_list[1].args[0]
    client.remove_pending_request.assert_called_once_with(first)


def test_unconfirmed_engage_returns_failure_after_bounded_retries(monkeypatch):
    from flexcell_skills import pick_server
    client = Mock()
    client.wait_for_service.return_value = True
    monkeypatch.setattr(pick_server, 'wait_future', lambda future, seconds: 'timeout')
    node = SimpleNamespace(_base='world', _carry_engage=client)
    assert not pick_server.PickServer._engage_carry(node, 'a', [0., 0., 0.])[0]
    assert client.call_async.call_count == 2
