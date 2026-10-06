"""Failure boundaries for the composition executor; no robot sampling here."""
import copy
import json
from pathlib import Path

import pytest

from flexcell_skills.contracts.composite import CompositeError, Journal, execute, validate_plan


PLAN = dict(scenario_id='swap', initial_objects={'a':[.22,0,.0175], 'b':[.20,-.18,.0175]},
            stages=[dict(stage_id='buffer',object_name='b',destination=[.12,-.15,.0175]),
                    dict(stage_id='a',object_name='a',destination=[.20,-.18,.0175]),
                    dict(stage_id='b',object_name='b',destination=[.22,0,.0175])],
            final_empty_positions=[[.12,-.15,.0175]],position_tolerance_m=.06,clearance_m=.05,motion_profile_id='demo_slow')


class Rig:
    def __init__(self):
        self.actual = copy.deepcopy(PLAN['initial_objects'])
        self.calls, self.events, self.observed = [], [], []
        self.canceled = False

    def observe(self, stage, boundary):
        self.observed.append((stage,boundary))
        return dict(outcome=0,error_code=0,source='SIMULATION_GROUND_TRUTH',revision=len(self.calls),
                    evidence_id='obs-'+str(len(self.observed)),carry=dict(engaged=False,object_id=''),
                    objects=[dict(name=k,available=True,position=v[:]) for k,v in self.actual.items()])

    def native(self, stage, goal_uuid):
        # The STARTED durability boundary precedes dispatch.
        assert self.events[-1]['event']=='STARTED' and self.events[-1]['component_goal_uuid']==goal_uuid
        self.calls.append(stage['stage_id'])
        self.actual[stage['object_name']]=stage['destination'][:]
        return dict(run_id='native-'+str(len(self.calls)),episode_path='test-native.json',goal_uuid=goal_uuid,terminal_status='SUCCEEDED',outcome=0,error_code=0,
                    object_at_place=True,final_position_error_m=.001,
                    final_state=dict(goal_uuid=goal_uuid,outcome='0',error_code=0,object_at_place=True,final_position_error_m=.001))

    def emit(self,event,**data):
        self.events.append(dict(event=event,**copy.deepcopy(data)))

    def run(self, **kwargs):
        return execute(copy.deepcopy(PLAN),kwargs.get('observe',self.observe),kwargs.get('native',self.native),
                       self.emit,lambda:self.canceled)


def test_swap_revisits_object_and_requires_independent_final_snapshot():
    rig=Rig(); result=rig.run()
    assert result['outcome']==0 and result['completed_stage_ids']==['buffer','a','b']
    assert len(set(result['component_goal_uuids']))==3
    assert rig.observed==[('buffer','before'),('buffer','after'),('a','before'),('a','after'),('b','before'),('b','after'),('','final')]
    assert [e['stage_id'] for e in rig.events if e['event']=='COMMITTED']==['buffer','a','b']


@pytest.mark.parametrize('mutation',[lambda p:p.update(position_tolerance_m=True),lambda p:p.update(position_tolerance_m=float('nan')),
    lambda p:p.update(position_tolerance_m=.061),lambda p:p.update(clearance_m=.049),lambda p:p.update(stages=[]),
    lambda p:p['stages'][1].update(stage_id='buffer'),lambda p:p['stages'][0].update(object_name='unknown'),
    lambda p:p['stages'][0].update(destination=[0,False,0]),lambda p:p['initial_objects'].update(a=[0,float('inf'),0]),
    lambda p:p.update(unregistered_field=True)])
def test_invalid_plan_never_dispatches(mutation):
    plan=copy.deepcopy(PLAN); mutation(plan); rig=Rig()
    result=execute(plan,rig.observe,rig.native,rig.emit)
    assert result['error_code']==60 and not rig.calls and not rig.observed


@pytest.mark.parametrize('mutation',[lambda o:o.update(outcome=False),lambda o:o.update(source='REAL_ROBOT'),
    lambda o:o.update(evidence_id=''),lambda o:o['carry'].update(engaged=0),lambda o:o['carry'].update(object_id='b'),
    lambda o:o['objects'][0].update(available=False),lambda o:o['objects'].append(o['objects'][0]),
    lambda o:o['objects'][0].update(position=[0,float('nan'),0])])
def test_missing_or_invalid_observation_never_dispatches(mutation):
    rig=Rig()
    def observe(*args):
        obs=rig.observe(*args);mutation(obs);return obs
    result=rig.run(observe=observe)
    assert result['error_code']==64 and not rig.calls


def test_occupied_destination_or_state_drift_stops_at_boundary():
    for xyz in ([.12,-.15,.0175],[.4,0,.0175]):
        rig=Rig();rig.actual['a']=xyz
        assert rig.run()['error_code']==61 and not rig.calls


@pytest.mark.parametrize('mutation',[lambda c:c.update(outcome=False),lambda c:c.update(terminal_status=None),
    lambda c:c.update(episode_path=None),
    lambda c:c.update(final_position_error_m=float('nan')),lambda c:c.update(object_at_place=False),
    lambda c:c['final_state'].update(goal_uuid='wrong'),lambda c:c['final_state'].update(error_code=51)])
def test_unknown_or_failed_native_terminal_preserved_without_next_stage(mutation):
    rig=Rig()
    def native(*args):
        c=rig.native(*args);mutation(c);return c
    result=rig.run(native=native)
    assert result['error_code']==62 and rig.calls==['buffer'] and not result['completed_stage_ids']
    assert len([e for e in rig.events if e['event']=='NATIVE_TERMINAL'])==1


def test_external_state_drift_after_verified_task_stops_before_next_stage():
    rig=Rig()
    def native(*args):
        c=rig.native(*args);rig.actual['a']=[.4,0,.0175];return c
    assert rig.run(native=native)['error_code']==63 and rig.calls==['buffer']


def test_cancel_after_native_terminal_never_dispatches_next_stage():
    rig=Rig()
    def native(*args):
        c=rig.native(*args);rig.canceled=True;return c
    result=rig.run(native=native)
    assert result['outcome']==2 and result['error_code']==32 and rig.calls==['buffer']
    assert result['component_run_ids']==['native-1'] and not result['completed_stage_ids']


def test_duplicate_native_run_id_rejected():
    rig=Rig()
    def native(*args):
        c=rig.native(*args);c['run_id']='same';return c
    result=rig.run(native=native)
    assert result['error_code']==62 and rig.calls==['buffer','a']


def test_final_joint_observation_failure_does_not_rewrite_committed_stages():
    rig=Rig()
    def observe(stage,boundary):
        if boundary=='final':rig.actual['b']=[.12,-.15,.0175]
        return rig.observe(stage,boundary)
    result=rig.run(observe=observe)
    assert result['error_code']==63 and result['completed_stage_ids']==['buffer','a','b']


def test_native_exception_preserves_started_without_replay():
    rig=Rig()
    def native(*args):raise RuntimeError('unknown terminal')
    result=rig.run(native=native)
    assert result['error_code']==2 and rig.events[-2]['event']=='STARTED'
    assert not result['completed_stage_ids']


def test_journal_is_exclusive_durable_and_preserves_nan_as_missing(tmp_path):
    j=Journal(tmp_path,'composite-one',dict(runtime_fingerprint='frozen'))
    j.emit('STARTED',stage_id='buffer',component_goal_uuid='id')
    # The event is visible before close, so a crash never creates fake completion.
    assert json.loads(j.path.read_text())['event']=='STARTED'
    with pytest.raises(FileExistsError):Journal(tmp_path,'composite-one',{})
    j.emit('NATIVE_TERMINAL',final_position_error_m=float('nan'));j.close()
    assert json.loads(j.path.read_text().splitlines()[1])['final_position_error_m'] is None
