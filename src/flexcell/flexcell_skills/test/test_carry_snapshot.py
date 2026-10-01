"""A stale transition topic must not override a current, confirmed snapshot."""
from types import SimpleNamespace
from unittest.mock import Mock
import json
import pytest

from flexcell_interfaces.msg import CarryState
from flexcell_skills import observe_server
from flexcell_skills.carry_server import CarryServer


def test_stale_a_topic_is_not_reused_for_next_object(monkeypatch):
    stale = CarryState(engaged=True, object_id='target_box_a')
    current = CarryState(engaged=False, object_id='')
    client = Mock()
    client.wait_for_service.return_value = True
    client.call_async.return_value.result.return_value = SimpleNamespace(
        success=True, state=current, revision=4, session='')
    node = SimpleNamespace(_carry_query=client, _carry=stale, _log=Mock())
    monkeypatch.setattr(observe_server, 'wait_future', lambda *_: 'done')
    actual = observe_server.ObserveServer._current_carry(node)
    assert not actual.engaged and actual.object_id == ''
    assert actual is not current  # snapshot cannot mutate the response/cache later
    assert stale.engaged and stale.object_id == 'target_box_a'


def test_unknown_carry_is_observation_failure_not_synthetic_off():
    client = Mock()
    client.wait_for_service.return_value = False
    with pytest.raises(observe_server.CarrySnapshotUnavailable):
        observe_server.ObserveServer._current_carry(SimpleNamespace(_carry_query=client))


def test_native_lease_expiry_cannot_be_reported_as_healthy_engagement():
    node = SimpleNamespace(_backend='velocity_servo', _offset=[0., 0., 0.],
                           _session='old', _object_id='a', _guard='/carry/',
                           _Empty=Mock(), _String=Mock(), _gz_node=Mock())
    node._gz_node.request.return_value = (True, SimpleNamespace(data=json.dumps(
        {'engaged': False, 'session': '', 'object': ''})))
    result = CarryServer._on_query(node, None, SimpleNamespace())
    assert not result.success and 'ownership' in result.detail


def test_status_reply_loss_retries_only_the_read_without_changing_ownership():
    node = SimpleNamespace(_backend='velocity_servo', _offset=None, _session='',
                           _object_id='', _guard='/carry/', _Empty=Mock(),
                           _String=Mock(), _gz_node=Mock(), _state_revision=4,
                           _state=Mock(return_value=CarryState(engaged=False)))
    reply = SimpleNamespace(data=json.dumps({'engaged': False, 'session': '', 'object': ''}))
    node._gz_node.request.side_effect = [(False, None), (True, reply)]
    result = CarryServer._on_query(node, None, SimpleNamespace())
    assert result.success and not result.state.engaged
    assert node._gz_node.request.call_count == 2
    assert all(c.args[0] == '/carry/status' and c.args[-1] == 400
               for c in node._gz_node.request.call_args_list)
    assert node._offset is None and node._session == ''


def test_all_status_replies_lost_fail_closed_with_a_bounded_wait():
    node = SimpleNamespace(_backend='velocity_servo', _offset=None, _session='',
                           _object_id='', _guard='/carry/', _Empty=Mock(),
                           _String=Mock(), _gz_node=Mock())
    node._gz_node.request.return_value = (False, None)
    result = CarryServer._on_query(node, None, SimpleNamespace())
    assert not result.success and '3 attempts' in result.detail
    assert node._gz_node.request.call_count == 3
