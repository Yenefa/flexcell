"""PLACE checks its own release dependency and keeps failed discovery evidence."""
from types import SimpleNamespace
from unittest.mock import Mock

from flexcell_interfaces.action import PlaceObject
from flexcell_skills.place_server import PlaceServer


def test_failed_discovery_logs_graph_without_claiming_graph_presence_is_ready():
    n = PlaceServer.__new__(PlaceServer)
    n._carry_release = Mock()
    n._carry_release.wait_for_service.return_value = False
    n._carry_release.service_is_ready.return_value = False
    n._release_service = '/flexcell/carry_release'
    n.get_service_names_and_types = lambda: [('/flexcell/carry_release', ['std_srvs/srv/Trigger'])]
    n.get_node_names_and_namespaces = lambda: [('carry_server', '/')]
    n._dependency_log = Mock()
    rec = dict(request_id='place', evidence_id='evidence')
    assert not n._release_ready(2, 'preflight', rec)
    event = n._dependency_log.write.call_args.args[0]
    assert event['ready'] is False and event['graph_services']
    assert event['client_ready_after_wait'] is False and event['evidence_id'] == 'evidence'


def test_unavailable_release_prevents_approach_motion():
    n = PlaceServer.__new__(PlaceServer)
    n._seq, n._admission = 0, __import__('threading').Lock()
    n._profiles, n._default_profile = ['demo_slow'], 'demo_slow'
    n._scene = SimpleNamespace(is_attached=lambda name: (True, ''))
    n._feedback = lambda *a: None
    n._release_ready = Mock(return_value=False)
    n._motion, n._log = Mock(), Mock()
    goal = PlaceObject.Goal()
    goal.object_name, goal.motion_profile_id = 'target_box_a', 'demo_slow'
    handle = SimpleNamespace(request=goal, abort=Mock(), is_cancel_requested=False)
    result = n._execute(handle)
    assert result.error_code == PlaceObject.Result.ERR_PLACE_FAILED
    assert not result.released
    assert 'before approach' in result.detail
    n._motion.assert_not_called()
