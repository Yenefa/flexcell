"""Pure task-result contracts, usable without a ROS installation."""
import copy
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

SOURCE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SOURCE))
from flexcell_skills.task_components.push_results import contact_push_result,legacy_push_result


def fixture():
    context=dict(parent_run_id='parent',stage_id='push_00',backend='finger_tcp',
                 goal_uuid='a'*32,request_id='request',run_id='request')
    world=NS(source='SIMULATION_GROUND_TRUTH',header=NS(frame_id='world'),
             carry=NS(engaged=False),robot=NS(has_gripper_state=True),
             objects=[NS(name=n,available=True,pose_age_s=.01) for n in ['red','blue']])
    reply=NS(goal_uuid=context['goal_uuid'],receipt_json=json.dumps(dict(request_id='request')),
        outcome=0,error_code=0,detail='',evidence_id='evidence',displacement_m=.0305,
        direction_cos=1.,lateral_m=0.,delta_z_m=0.,contact_made=True,contact_lost=False,
        carry_engaged_during=False,stroke_outcome=0,stroke_error_code=0,motion_terminal_known=True,
        return_completed=True,arm_ready=True,has_returned_state=True,physical_contact_observed=True,
        returned_state=world,observed_monotonic_ns=900_000_000,motion_goals_used=12)
    return reply,context


class PushResultTest(unittest.TestCase):
    def convert(self,reply,context,budget=28,clock=None):
        return contact_push_result(reply,context,{'red':[.22,0.,.0175],'blue':[.2,-.18,.0175]},
                                   budget,context['goal_uuid'],clock or (lambda:1_000_000_000))

    def test_module_import_has_no_ros_dependency(self):
        code='import sys; sys.path.insert(0,'+repr(str(SOURCE))+'); import flexcell_skills.task_components.push_results; assert "rclpy" not in sys.modules'
        subprocess.run([sys.executable,'-I','-c',code],check=True)

    def test_conversion_keeps_inputs_and_uses_injected_clock_once(self):
        reply,context=fixture();original_reply=copy.deepcopy(reply);original_context=copy.deepcopy(context)
        clock=Mock(return_value=1_000_000_000)
        result=self.convert(reply,context,clock=clock)
        self.assertEqual(result['outcome'],0);self.assertEqual(result['receipt_age_s'],.1)
        clock.assert_called_once_with()
        self.assertEqual(reply,original_reply);self.assertEqual(context,original_context)

    def test_stroke_success_without_return_does_not_commit(self):
        reply,context=fixture();reply.return_completed=False
        result=self.convert(reply,context)
        self.assertEqual((result['outcome'],result['error_code']),(1,62))

    def test_expired_or_mismatched_return_does_not_commit(self):
        for kind in ('expired','wrong_uuid','missing_object'):
            with self.subTest(kind=kind):
                reply,context=fixture()
                if kind=='expired':reply.observed_monotonic_ns=100_000_000
                elif kind=='wrong_uuid':reply.goal_uuid='b'*32
                else:reply.returned_state.objects.pop()
                self.assertEqual(self.convert(reply,context)['outcome'],1)

    def test_unknown_terminal_remains_unknown(self):
        reply,context=fixture();reply.motion_terminal_known=False
        result=self.convert(reply,context)
        self.assertEqual((result['outcome'],result['error_code']),(3,33))

    def test_budget_overrun_is_not_success(self):
        reply,context=fixture()
        self.assertEqual(self.convert(reply,context,budget=-1)['outcome'],1)

    def test_cancellation_status_is_preserved(self):
        reply,context=fixture();reply.outcome=2;reply.error_code=32
        self.assertEqual(self.convert(reply,context)['terminal_status'],'CANCELED')

    def test_legacy_result_keeps_request_fallback_and_measurements(self):
        reply,context=fixture();reply.run_id=''
        result=legacy_push_result(reply,context,'legacy-request','SUCCEEDED',context['goal_uuid'])
        self.assertEqual(result['run_id'],'legacy-request')
        self.assertEqual(result['displacement_m'],.0305)
        self.assertEqual(result['final_state']['goal_uuid'],context['goal_uuid'])


if __name__=='__main__':unittest.main()
