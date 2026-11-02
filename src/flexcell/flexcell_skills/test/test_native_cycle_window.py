"""A detached reference and complete raw evidence are required for native cycles."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'scripts'))
from native_cycle_gate import verify_cycle, verify_run


@pytest.fixture(scope='module')
def evidence():
    declaration = json.loads((ROOT/'infra/native-five-cycle-window.json').read_text())
    step, ref = 2_000_000, 2_000_000_000
    first = ref+2*step; last = first+declaration['hold_ns']; release = last+step; settled = release+1_000_000_000
    mono = lambda ns:10**12+2*ns
    name, token = 'target_box_a','a'*32
    cycle = dict(index=0,object=name,session=token,previous_session='',reference_sim_ns=ref,retired_probe_sim_ns=settled)
    physics,contacts = {},{}
    def target(own,pose,force):
        data = dict(collision_entity=own,pose=pose.copy(),component_present=True,contacts={})
        if force:
            data['contacts'] = dict(contact=[dict(collision1=dict(id=str(own)),collision2=dict(id='9'),position=[{}],
                wrench=[dict(body_1_wrench=dict(force=dict(z=.49)),body_2_wrench=dict(force=dict(z=-.49)))])])
        return data
    for ns in range(ref-1_000_000_000,settled+step,step):
        z = .0175 if ns < ref else max(.0175,.22-4.9*max(0.,(ns-release)/1e9)**2)
        a = [.35,.18,z,0.,0.,0.,1.]; b = [.20,-.18,.0175,0.,0.,0.,1.]
        clock = dict(sim_ns=ns,step_ns=step,monotonic_ns=mono(ns))
        physics[ns] = dict(clock,parent_pose=[.1,0.,.2,0.,0.,0.,1.],objects={
            name:dict(pose=a,joint_component=first<=ns<=last),'target_box_b':dict(pose=b,joint_component=False)})
        contacts[ns] = dict(clock,schema_version=1,source='ECM_POST_PHYSICS',targets={
            name:target(7,a,z==.0175),'target_box_b':target(8,b,True),
            'ground_plane':dict(collision_entity=9,pose=[0.,0.,0.,0.,0.,0.,1.],component_present=False,contacts=None)})
    detached = dict(ready=True,engaged=False,session='',component_present=[False,False],sim_ns=ref-step)
    active = dict(ready=True,engaged=True,session=token,object=name,component_present=[True,False])
    events = []
    def call(label,operation,at,reply,*,session='',obj='',pose=None):
        events.append(dict(cycle=0,label=label,operation=operation,object=obj,session=session,pose=pose,
            request_mono_ns=at,reply_mono_ns=at+100,transport_ok=True,reply=deepcopy(reply)))
    call('before_preposition','status',mono(ref-step)-5000,detached)
    call('preposition','set_pose',mono(ref)-3000,True,obj=name,pose=declaration['preposition_poses'][name])
    call('engage','engage',mono(ref)+1000,True,session=token,obj=name,pose=physics[ref]['objects'][name]['pose'])
    call('reject_other_engage','engage',mono(first)+1000,False,session='b'*32,obj='target_box_b',pose=b)
    call('reject_other_pin','pin',mono(first)+2000,False,session=token,obj='target_box_b',pose=b)
    call('after_probes','status',mono(first)+3000,active)
    call('heartbeat','pin',mono(first)+4000,True,session=token,obj=name,pose=a)
    call('release','release',mono(release)-50,True,session=token)
    call('after_release','status',mono(settled)+1000,detached)
    call('reject_retired_engage','engage',mono(settled)+2000,False,session=token,obj=name,pose=physics[settled]['objects'][name]['pose'])
    call('final_status','status',mono(settled)+3000,detached)
    return physics,contacts,cycle,events,declaration


def test_detached_preposition_reference_survives_entire_cycle(evidence):
    p,c,cycle,events,declaration = evidence
    result = verify_cycle(p,c,cycle,events,declaration)
    assert result['status'] == 'NATIVE_CYCLE_PASS' and result['reference_bind_gap_ns'] == 4_000_000
    assert result['attached_duration_s'] == 10.1 and result['passive_force_samples'] == 500
    assert result['freefall']['acceleration_m_s2'] == pytest.approx(-9.8)


@pytest.mark.parametrize('defect',['attached_reference','missing_step','prebind_drift','unknown_force',
                                  'retired_accepted','distant_retired_pose','looser_limit'])
def test_bad_or_ambiguous_cycle_evidence_cannot_pass(evidence,defect):
    p,c,cycle,events,declaration = deepcopy(evidence)
    ref=cycle['reference_sim_ns']
    if defect == 'attached_reference': p[ref]['objects'][cycle['object']]['joint_component'] = True
    elif defect == 'missing_step': p.pop(ref+2_000_000)
    elif defect == 'prebind_drift':
        p[ref+2_000_000]['objects'][cycle['object']]['pose'][2] -= .003
        c[ref+2_000_000]['targets'][cycle['object']]['pose'][2] -= .003
    elif defect == 'unknown_force':
        c[ref]['targets']['target_box_b']['contacts']['contact'][0]['wrench'] = []
    elif defect == 'retired_accepted': next(e for e in events if e['label']=='reject_retired_engage')['reply']=True
    elif defect == 'distant_retired_pose': next(e for e in events if e['label']=='reject_retired_engage')['pose']=[0.,0.,5.,0.,0.,0.,1.]
    else: declaration['translation_limit_m']=.003
    with pytest.raises(ValueError): verify_cycle(p,c,cycle,events,declaration)


def test_fewer_than_five_cycles_cannot_be_relabelled_complete(tmp_path,evidence):
    (tmp_path/'worker.json').write_text(json.dumps(dict(status='PASS',cycles=[evidence[2]])))
    with pytest.raises(ValueError,match='five cycles'): verify_run(tmp_path,evidence[4])


def test_first_unready_native_guard_stops_without_preposition_or_replacement(tmp_path,monkeypatch,evidence):
    import native_cycle_window
    calls=[]
    class Node:
        def request(self,path,*_):
            calls.append(path)
            return True,SimpleNamespace(data=json.dumps(dict(ready=False,engaged=False,component_present=[False,False])))
    gz=ModuleType('gz');transport=ModuleType('gz.transport13');transport.Node=Node;gz.transport13=transport
    msgs=ModuleType('gz.msgs10')
    for name,typ in [('empty_pb2','Empty'),('stringmsg_pb2','StringMsg'),('boolean_pb2','Boolean'),('pose_pb2','Pose')]:
        setattr(msgs,name,SimpleNamespace(**{typ:type(typ,(),{})}))
    for name,value in [('gz',gz),('gz.transport13',transport),('gz.msgs10',msgs)]: monkeypatch.setitem(sys.modules,name,value)
    for name in ('physics_steps.jsonl','contact_steps.jsonl'): (tmp_path/name).touch()
    assert native_cycle_window.worker(tmp_path,'empty',evidence[4]) == 1
    result=json.loads((tmp_path/'worker.json').read_text())
    assert result['status']=='STOPPED' and len(result['cycles'])==1
    assert calls==['/world/empty/flexcell/carry/status']


def test_live_consumer_starts_at_new_records_without_erasing_raw_history(tmp_path):
    from native_cycle_window import Follower
    history = (json.dumps(dict(sim_ns=1,startup=True))+'\n')*10000
    for name in ('physics_steps.jsonl','contact_steps.jsonl'): (tmp_path/name).write_text(history)
    follower = Follower(tmp_path)
    for name in ('physics_steps.jsonl','contact_steps.jsonl'):
        with (tmp_path/name).open('a') as stream:
            for ns in (2,4): stream.write(json.dumps(dict(sim_ns=ns))+'\n')
    assert follower.collect() == [4]
    assert list(follower.tables[0]) == list(follower.tables[1]) == [4]
    for name in ('physics_steps.jsonl','contact_steps.jsonl'):
        assert (tmp_path/name).read_text().startswith(history)


@pytest.mark.parametrize('case',['pretrigger_history','stale_eligible','stale_producer'])
def test_reference_epoch_selection_preserves_both_freshness_bounds(tmp_path,monkeypatch,case):
    import native_cycle_window as module
    for name in ('physics_steps.jsonl','contact_steps.jsonl'): (tmp_path/name).touch()
    follower=module.Follower(tmp_path)
    now=10**12
    follower.tables=[{1:dict(sim_ns=1,monotonic_ns=now-2_000_000_000),
                     2:dict(sim_ns=2,monotonic_ns=now-1_000_000)}, {1:{},2:{}}]
    monkeypatch.setattr(follower,'collect',lambda:[1,2])
    monkeypatch.setattr(module.time,'monotonic_ns',lambda:now)
    if case=='stale_producer': follower.tables[0][2]['monotonic_ns']=now-500_000_001
    condition=(lambda p,c:True) if case=='stale_eligible' else (lambda p,c:p['sim_ns']>=2)
    if case=='pretrigger_history': assert follower.wait(condition,earliest=True)[0]['sim_ns']==2
    else:
        with pytest.raises(ValueError,match='stale'): follower.wait(condition,earliest=True)


@pytest.mark.parametrize('mode',['detached_catchup','stale_reference','active_watch','physics_stale','contact_stale'])
def test_source_watermark_does_not_excuse_stale_reference_or_active_watch(tmp_path,monkeypatch,mode):
    import native_cycle_window as module
    now=10**12
    for name in ('physics_steps.jsonl','contact_steps.jsonl'):
        (tmp_path/name).write_text(json.dumps(dict(sim_ns=2,monotonic_ns=now-1_000_000))+'\n')
    if mode.endswith('_stale'):
        name='physics_steps.jsonl' if mode=='physics_stale' else 'contact_steps.jsonl'
        (tmp_path/name).write_text(json.dumps(dict(sim_ns=2,monotonic_ns=now-500_000_001))+'\n')
    follower=module.Follower(tmp_path)
    count=0
    def collect():
        nonlocal count
        count+=1
        rows={1:dict(sim_ns=1,monotonic_ns=now-1_160_000_000)}
        if count>1: rows[2]=dict(sim_ns=2,monotonic_ns=now-1_000_000)
        follower.tables=[rows,{ns:{} for ns in rows}]
        return sorted(rows)
    monkeypatch.setattr(follower,'collect',collect)
    monkeypatch.setattr(module.time,'monotonic_ns',lambda:now)
    if mode=='detached_catchup':
        assert follower.wait(lambda *_:True)[0]['sim_ns']==2
    else:
        with pytest.raises(ValueError,match='stale'):
            follower.wait(lambda *_:True,earliest=mode=='stale_reference',
                          watch=(lambda *_:None) if mode=='active_watch' else None)


def test_collect_stops_at_captured_end_without_dropping_appended_records(tmp_path):
    import io
    from native_cycle_window import Follower
    for name in ('physics_steps.jsonl','contact_steps.jsonl'): (tmp_path/name).touch()
    follower=Follower(tmp_path)
    for stream in follower.streams:stream.close()
    class Growing(io.StringIO):
        def __init__(self):
            super().__init__(json.dumps(dict(sim_ns=2))+'\n');self.appended=False
        def readline(self,*args):
            value=super().readline(*args)
            if not self.appended:
                position=self.tell();self.seek(0,2);self.write(json.dumps(dict(sim_ns=3))+'\n');self.seek(position)
                self.appended=True
            return value
    follower.streams=[Growing(),Growing()];follower.align_new_record=[False,False]
    assert follower.collect()==[2]
    assert follower.collect()==[2,3]
