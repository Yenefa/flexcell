"""Unknown controller acceptance blocks the real motion admission seam."""
from types import SimpleNamespace
import threading
import time

import pytest
from moveit_msgs.msg import RobotTrajectory
from flexcell_interfaces.action import MoveToPose
from flexcell_skills.move_to_pose_server import MoveToPoseServer


class Future:
    def __init__(self, response=None, done=False):
        self.response, self.ready = response, done

    def done(self):
        return self.ready

    def result(self):
        return self.response


def node(backend='controller_action'):
    n = MoveToPoseServer.__new__(MoveToPoseServer)
    n._backend, n._fjt_action, n._exec_act = backend, '/fake_controller', '/fake_execute'
    n._admission, n._backend_guard = threading.Lock(), threading.Lock()
    n._pending_backend_goals, n._motion_blocked = {}, False
    n._motion_blocked_reason, n._enforce_ori = '', False
    n._active_motion_ids = ('test', 'evidence')
    n._seq = 0
    n._feedback = lambda *a: None
    n.records = []
    n._log = n.records.append
    n._controller_event_log = n.records.append
    return n


@pytest.mark.parametrize('backend', ['controller_action', 'moveit_execute_trajectory'])
def test_late_controller_acceptance_cancels_original_and_does_not_resend(backend):
    n = node(backend)
    send, result = Future(), Future()
    requests, cancels = [], []
    def dispatch(goal, goal_uuid=None):
        requests.append(goal_uuid)
        return send
    client = SimpleNamespace(wait_for_server=lambda **k: True, send_goal_async=dispatch)
    n._fjt_client = n._exec_client = client
    n._wait = lambda *args: 'timeout'
    status, _, _, _ = n._send_for_execution(RobotTrajectory(), time.monotonic()+1)
    assert status == 'send_timeout' and n._motion_blocked and len(requests) == 1
    n._poll_backend_goals()
    assert n._pending_backend_goals
    send.response = SimpleNamespace(accepted=True, cancel_goal_async=lambda: cancels.append(True),
                                    get_result_async=lambda: result)
    send.ready = True
    n._poll_backend_goals()
    assert len(cancels) == 1 and n._pending_backend_goals
    result.ready, result.response = True, SimpleNamespace(status=5, result=None)
    n._poll_backend_goals()
    assert not n._pending_backend_goals and len(requests) == len(cancels) == 1
    assert all(r['controller_goal_uuid'] == bytes(requests[0].uuid).hex() for r in n.records)


def test_fresh_stationary_state_cannot_release_unknown_controller_goal():
    n = node()
    n._quarantine_backend(Future(), 'unknown')
    reconfirmations = []
    n._reconfirm_state = lambda: reconfirmations.append(True) or True
    terminals = []
    handle = SimpleNamespace(request=MoveToPose.Goal(), goal_id=SimpleNamespace(uuid=[0]*16),
                             abort=lambda: terminals.append('abort'))
    result = n._execute(handle)
    assert result.outcome == MoveToPose.Result.OUTCOME_STATE_UNKNOWN
    assert result.error_code == MoveToPose.Result.ERR_STATE_UNKNOWN
    assert reconfirmations == [] and terminals == ['abort']
    assert not n._admission.locked()


def test_send_exception_does_not_invent_rejection_or_release_admission():
    n = node()
    def dispatch(*args, **kwargs):
        raise RuntimeError('send transport unknown')
    n._fjt_client = SimpleNamespace(wait_for_server=lambda **k: True, send_goal_async=dispatch)
    status, _, _, _ = n._send_for_execution(RobotTrajectory(), time.monotonic()+1)
    assert status == 'send_unknown' and n._motion_blocked
    n._poll_backend_goals()
    assert n._pending_backend_goals
