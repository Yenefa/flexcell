"""The swap needs a second B task and a fresh joint success predicate."""

import copy
import json
from pathlib import Path
import unittest

import t3_swap_pilot as pilot


class SwapTests(unittest.TestCase):
    def setUp(self):
        self.result=dict(outcome_val=0, carry=dict(engaged=False,object_id=''),objects=[
            dict(name=pilot.OBJECTS[0],available=True,position=pilot.base.SOURCE[pilot.OBJECTS[1]]),
            dict(name=pilot.OBJECTS[1],available=True,position=pilot.base.SOURCE[pilot.OBJECTS[0]])])
        self.components=[dict(stage_id=s[0],run_id='run-'+str(i),outcome='SUCCEEDED',harness_error=None)
                         for i,s in enumerate(pilot.STAGES)]

    def test_swap_requires_all_three_ordered_distinct_native_tasks(self):
        self.assertTrue(pilot.composite_pass(self.components,self.result))
        self.assertFalse(pilot.composite_pass(self.components[:2],self.result))
        self.assertFalse(pilot.composite_pass(self.components[::-1],self.result))
        values=copy.deepcopy(self.components);values[2]['run_id']=values[0]['run_id']
        self.assertFalse(pilot.composite_pass(values,self.result))

    def test_old_success_cannot_substitute_for_joint_fresh_measurement(self):
        for mutation in ('unswapped','missing','unavailable','carry','nan','duplicate'):
            result=copy.deepcopy(self.result)
            if mutation=='unswapped': result['objects'][0]['position']=pilot.base.SOURCE[pilot.OBJECTS[0]]
            if mutation=='missing': result['objects'].pop()
            if mutation=='unavailable': result['objects'][1]['available']=False
            if mutation=='carry': result['carry']['engaged']=True
            if mutation=='nan': result['objects'][1]['position'][0]=float('nan')
            if mutation=='duplicate': result['objects'].append(result['objects'][0])
            self.assertFalse(pilot.composite_pass(self.components,result),mutation)

    def test_buffer_occupancy_and_failure_are_not_hidden(self):
        positions=copy.deepcopy(pilot.base.SOURCE)
        self.assertFalse(pilot.vacant(positions,pilot.base.SOURCE[pilot.OBJECTS[1]],pilot.OBJECTS[0]))
        self.assertTrue(pilot.vacant(positions,pilot.BUFFER,pilot.OBJECTS[1]))
        values=copy.deepcopy(self.components);values[1]['outcome']='FAILED'
        self.assertFalse(pilot.composite_pass(values,self.result))
        values=copy.deepcopy(self.components);values[1]['harness_error']='goal unknown'
        self.assertFalse(pilot.composite_pass(values,self.result))

    def test_native_requires_verified_same_goal_and_canonical_outcomes(self):
        target=pilot.OBJECTS[1]
        final=dict(outcome='0',error_code=0,goal_uuid='uuid',object_at_place=True,final_position_error_m=.01)
        result=dict(final,outcome_val=0,skip_verify=False)
        episode=dict(run_id='native-run',final_state=final,steps=[dict(policy_input=dict(goal=dict(assignments=[[target,'task_place']])),
                     policy_output=dict(action=action,target=target),executor_result=dict(outcome=0)) for action in ('PICK','PLACE','VERIFY')])
        self.assertTrue(pilot.single_pass(episode,result,0,target))
        for code in (-6,134,None): self.assertFalse(pilot.single_pass(episode,result,code,target))
        for key,value in (('skip_verify',True),('goal_uuid','other'),('final_position_error_m',float('nan')),('outcome_val',False)):
            self.assertFalse(pilot.single_pass(episode,dict(result,**{key:value}),0,target))
        for value in (False,0.0,'00','0.0',None):
            altered=copy.deepcopy(episode);altered['final_state']['outcome']=value
            self.assertFalse(pilot.single_pass(altered,result,0,target))

    def test_real_native_episodes_and_final_joint_observe(self):
        root=Path(__file__).resolve().parents[1]/'acceptance/transferbench_t3_20261006'
        count=0
        for arm in ('fsm','hybrid'):
            parent=json.loads((root/arm/'composite/summary.json').read_text())
            self.assertTrue(pilot.composite_pass(parent['components'],parent['final_observe']))
            for path in (root/arm).glob('**/episode.json'):
                summary=json.loads((path.parent/'summary.json').read_text())
                client=json.loads((path.parent/'client.json').read_text())
                episode=json.loads(path.read_text());result=pilot.base.result_from_output(client['stdout'])
                self.assertEqual(episode['final_state']['outcome'],'0')
                if summary['target']:
                    self.assertTrue(pilot.single_pass(episode,result,client['return_code'],summary['target']))
                else:
                    self.assertTrue(pilot.base.success_predicate(episode,result,client['return_code']))
                count+=1
        self.assertEqual(count,8)

    def test_report_rechecks_real_receipts_without_modifying_ledger(self):
        import report_t3_swap
        root=Path(__file__).resolve().parents[1]/'acceptance/transferbench_t3_20261006'
        before=(root/'cost.jsonl').read_bytes()
        result=report_t3_swap.report(root)
        self.assertEqual(result['native_episode_count'],8)
        self.assertTrue(all(a['composite_outcome']=='SUCCEEDED' for a in result['arms']))
        self.assertTrue(all(a['unknown_or_quarantined_transport_events']==0 for a in result['arms']))
        self.assertEqual((root/'cost.jsonl').read_bytes(),before)


if __name__=='__main__':unittest.main()
