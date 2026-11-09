"""Resume only a proven prefix; never repeat a claimed or uncertain stage."""
from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import json
from pathlib import Path

import pytest

from flexcell_skills.contracts.composite import CompositeError, execute
from flexcell_skills.contracts.composite_checkpoint import claim_checkpoint, load_checkpoint, validate_paused
from flexcell_skills.contracts.episode import _sanitize
from test_composite import PLAN, Rig

FP='1'*64
SOURCE='composite-'+'a'*16


def paused(tmp_path):
    rig=Rig();episodes=tmp_path/'episodes';episodes.mkdir()
    def native(stage,goal_id):
        component=rig.native(stage,goal_id)
        component['final_state'].update(parent_run_id=SOURCE,stage_id=stage['stage_id'],execution_kind='IN_PROCESS_COMPONENT',component_execution_id=goal_id)
        path=episodes/(component['run_id']+'.json');component['episode_path']=str(path)
        episode=dict(run_id=component['run_id'],runtime_fingerprint=FP,policy=dict(name='hybrid',version='1.1'),final_state=_sanitize(component['final_state']),
                     steps=[dict(policy_input=dict(goal=dict(assignments=[[stage['object_name'],'task_place']])),
                                 policy_output=dict(action=action,target=stage['object_name']),executor_result=dict(outcome=0)) for action in ['PICK','PLACE','VERIFY']])
        path.write_text(json.dumps(episode));return component
    result=execute(copy.deepcopy(PLAN),rig.observe,native,rig.emit,pause_after_stages=1)
    assert result['outcome']==3 and rig.calls==['buffer'] and rig.observed==[('buffer','before'),('buffer','after')]
    events=[dict(event,seq=index,record_kind='ACTUAL_COMPOSITE_TASK',run_id=SOURCE,goal_uuid='b'*32,
                 runtime_fingerprint=FP,policy='hybrid',policy_version='1.1',contract_version=2) for index,event in enumerate(rig.events)]
    path=tmp_path/(SOURCE+'.jsonl');path.write_text(''.join(json.dumps(e)+'\n' for e in events))
    return rig,events,path,episodes


def load(path,episodes):
    return load_checkpoint(path.parent,SOURCE,hashlib.sha256(path.read_bytes()).hexdigest(),PLAN,FP,episodes)


def test_paused_prefix_continues_only_remaining_native_stages(tmp_path):
    rig,events,path,episodes=paused(tmp_path);checkpoint=load(path,episodes);rig.events=[]
    result=execute(copy.deepcopy(PLAN),rig.observe,rig.native,rig.emit,checkpoint=checkpoint)
    assert result['outcome']==0 and rig.calls==['buffer','a','b']
    assert result['completed_stage_ids']==['buffer','a','b'] and result['component_run_ids']==['native-1','native-2','native-3']
    assert len([e for e in rig.events if e['event']=='STARTED'])==2
    assert rig.events[1]['event']=='RESUME'


@pytest.mark.parametrize('mutation',[lambda e:e[-1].update(outcome=False),lambda e:e[-1].update(outcome=2),
    lambda e:e[-1].update(outcome=1),lambda e:e.pop(),lambda e:e[-1].update(completed_stage_ids=[]),
    lambda e:e[0].update(contract_version=1),lambda e:e[0].update(pause_after_stages=True),
    lambda e:e[2].update(component_goal_uuid='wrong'),lambda e:e[4]['observation']['carry'].update(engaged=True),
    lambda e:e[5].update(expected_positions=PLAN['initial_objects']),lambda e:e.insert(-1,copy.deepcopy(e[2]))])
def test_failed_unknown_or_corrupt_prefix_never_authorizes_resume(tmp_path,mutation):
    rig,events,path,episodes=paused(tmp_path);mutation(events)
    with pytest.raises((CompositeError,KeyError,ValueError)):
        validate_paused(events,PLAN,FP,lambda c:json.loads(Path(c['episode_path']).read_text()))
    assert rig.calls==['buffer']


def test_hash_plan_and_runtime_mismatch_rejected(tmp_path):
    rig,events,path,episodes=paused(tmp_path);sha=hashlib.sha256(path.read_bytes()).hexdigest()
    changed=copy.deepcopy(PLAN);changed['stages'][-1]['destination'][0]+=.01
    for plan,fp,digest in [(PLAN,'2'*64,sha),(changed,FP,sha),(PLAN,FP,'0'*64)]:
        with pytest.raises(CompositeError):load_checkpoint(tmp_path,SOURCE,digest,plan,fp,episodes)


def test_missing_or_modified_native_episode_rejected(tmp_path):
    rig,events,path,episodes=paused(tmp_path)
    episode=next(episodes.glob('*.json'));record=json.loads(episode.read_text());record['final_state']['error_code']=51
    episode.write_text(json.dumps(record))
    with pytest.raises(CompositeError):load(path,episodes)
    episode.unlink()
    with pytest.raises(CompositeError):load(path,episodes)


def test_server_storage_and_path_traversal_boundaries(tmp_path):
    rig,events,path,episodes=paused(tmp_path);digest=hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(CompositeError):load_checkpoint(tmp_path,'../outside',digest,PLAN,FP,episodes)
    outside=tmp_path/'external';outside.mkdir()
    with pytest.raises(CompositeError):load_checkpoint(tmp_path,SOURCE,digest,PLAN,FP,outside)


def test_current_state_drift_stops_without_new_native_dispatch(tmp_path):
    rig,events,path,episodes=paused(tmp_path);checkpoint=load(path,episodes);rig.events=[];rig.actual['a']=[.4,0,.0175]
    result=execute(PLAN,rig.observe,rig.native,rig.emit,checkpoint=checkpoint)
    assert result['error_code']==61 and rig.calls==['buffer']


def test_resume_cannot_pause_again_or_replay_completed_prefix(tmp_path):
    rig,events,path,episodes=paused(tmp_path);checkpoint=load(path,episodes);rig.events=[]
    result=execute(PLAN,rig.observe,rig.native,rig.emit,checkpoint=checkpoint,pause_after_stages=2)
    assert result['error_code']==65 and rig.calls==['buffer']


def test_atomic_claim_rejects_concurrent_and_restarted_attempts(tmp_path):
    rig,events,path,episodes=paused(tmp_path);checkpoint=load(path,episodes)
    def claim(index):
        try:return claim_checkpoint(tmp_path,checkpoint,'composite-'+format(index,'016x'))
        except CompositeError:return None
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(claim,range(4)))
    assert len([r for r in results if r])==1
    with pytest.raises(CompositeError):claim_checkpoint(tmp_path,load(path,episodes),'composite-'+'f'*16)
    assert path.read_bytes()==(''.join(json.dumps(e)+'\n' for e in events)).encode()


@pytest.mark.parametrize('value',[-1,True,3,4])
def test_invalid_pause_count_does_not_dispatch(value):
    rig=Rig();result=execute(PLAN,rig.observe,rig.native,rig.emit,pause_after_stages=value)
    assert result['error_code']==60 and not rig.calls and not rig.observed
