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
    assert result.get('failure_monotonic_ns', 0) > 0
    assert 'not explicitly detached' in result.get('failure_traceback', '')
    assert result['live_reader']['latest_rows'] == [None, None]


def test_completed_audit_rows_are_released_before_next_live_cycle(tmp_path, monkeypatch):
    import weakref
    import native_cycle_window as module

    declaration = json.loads((ROOT/'infra/native-five-cycle-window.json').read_text())
    references, alive_at_cycle_start = [], []
    original_loads = json.loads

    class AuditRow(dict):
        pass

    def loads(value, *args, **kwargs):
        row = original_loads(value, *args, **kwargs)
        if isinstance(row, dict) and row.get('audit_payload'):
            row = AuditRow(row)
            references.append(weakref.ref(row))
        return row

    class Data(list):
        def add(self):
            item = SimpleNamespace(key='', value=[])
            self.append(item)
            return item

    class Pose:
        def __init__(self):
            self.name = ''
            self.position = SimpleNamespace(x=0., y=0., z=0.)
            self.orientation = SimpleNamespace(x=0., y=0., z=0., w=1.)
            self.header = SimpleNamespace(data=Data())

    class Node:
        def __init__(self):
            self.owner, self.name, self.retired = '', '', set()

        def request(self, path, message, *_):
            operation = path.rsplit('/', 1)[-1]
            token = (message.header.data[0].value[0] if isinstance(message, Pose) and message.header.data
                     else getattr(message, 'data', ''))
            if operation == 'status':
                value = json.dumps(dict(ready=True, engaged=bool(self.owner), session=self.owner,
                    object=self.name, component_present=[bool(self.owner) and self.name==n
                        for n in declaration['preposition_poses']]))
            elif operation == 'set_pose':
                value = True
            elif operation == 'engage':
                value = not self.owner and token not in self.retired
                if value:
                    self.owner, self.name = token, message.name
            elif operation == 'release':
                value = bool(self.owner) and token == self.owner
                if value:
                    self.retired.add(token)
                    self.owner, self.name = '', ''
            else:
                value = bool(self.owner) and token == self.owner and message.name == self.name
            return True, SimpleNamespace(data=value)

    class Follower:
        def __init__(self, _):
            self.streams = []
            alive_at_cycle_start.append(sum(reference() is not None for reference in references))

        def wait(self, *_args, **_kwargs):
            return dict(sim_ns=1, monotonic_ns=1, parent_pose=[0.,0.,0.,0.,0.,0.,1.],
                objects={name:dict(pose=pose.copy(), joint_component=False)
                    for name,pose in declaration['preposition_poses'].items()}), {}

    gz=ModuleType('gz'); transport=ModuleType('gz.transport13'); transport.Node=Node; gz.transport13=transport
    msgs=ModuleType('gz.msgs10')
    for name, typ in [('empty_pb2','Empty'), ('stringmsg_pb2','StringMsg'), ('boolean_pb2','Boolean')]:
        setattr(msgs,name,SimpleNamespace(**{typ:SimpleNamespace}))
    msgs.pose_pb2=SimpleNamespace(Pose=Pose)
    for name,value in [('gz',gz),('gz.transport13',transport),('gz.msgs10',msgs)]:
        monkeypatch.setitem(sys.modules,name,value)
    monkeypatch.setattr(module,'Follower',Follower)
    monkeypatch.setattr(module,'verify_cycle',lambda *_args:dict(status='NATIVE_CYCLE_PASS'))
    monkeypatch.setattr(module.json,'loads',loads)
    payload = json.dumps(dict(sim_ns=1, targets={}, audit_payload=True))+'\n'
    for name in ('physics_steps.jsonl','contact_steps.jsonl'):
        (tmp_path/name).write_text(payload)

    assert module.worker(tmp_path,'empty',declaration) == 0
    assert len(references) == 2  # each raw row is parsed once, never again in later cycles
    assert alive_at_cycle_start == [0, 0, 0, 0, 0]


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


def test_incremental_audit_preserves_full_cycle_verdicts_and_raw_bytes(tmp_path,evidence):
    from native_cycle_window import audit_cycle
    offsets = {}
    for attempt in range(2):
        p,c,cycle,events,declaration = deepcopy(evidence)
        delta = attempt*20_000_000_000
        for table in (p,c):
            for row in table.values():
                row['sim_ns'] += delta
                row['monotonic_ns'] += 2*delta
        p,c = ({row['sim_ns']:row for row in table.values()} for table in (p,c))
        cycle['reference_sim_ns'] += delta
        cycle['retired_probe_sim_ns'] += delta
        for event in events:
            event['request_mono_ns'] += 2*delta
            event['reply_mono_ns'] += 2*delta
            if isinstance(event['reply'],dict) and 'sim_ns' in event['reply']:
                event['reply']['sim_ns'] += delta
        expected = verify_cycle(p,c,cycle,events,declaration)
        for name,records in [('physics_steps.jsonl',p.values()),
                             ('contact_steps.jsonl',c.values()),('native-events.jsonl',events)]:
            with (tmp_path/name).open('a') as stream:
                stream.writelines(json.dumps(row)+'\n' for row in records)
        before = {path.name:path.read_bytes() for path in tmp_path.iterdir()}
        assert audit_cycle(tmp_path,cycle,declaration,offsets) == expected
        assert {path.name:path.read_bytes() for path in tmp_path.iterdir()} == before


def test_incremental_audit_rejects_duplicates_across_read_boundaries(tmp_path,monkeypatch):
    import native_cycle_window as module
    monkeypatch.setattr(module,'verify_cycle',lambda *args: {})
    offsets = {}
    for name in ('physics_steps.jsonl','contact_steps.jsonl','native-events.jsonl'):
        (tmp_path/name).write_text('{"sim_ns":1,"targets":{}}\n')
    module.audit_cycle(tmp_path,{}, {},offsets)
    with (tmp_path/'physics_steps.jsonl').open('a') as stream:
        stream.write('{"sim_ns":1}\n')
    with pytest.raises(ValueError,match='duplicate or reordered'):
        module.audit_cycle(tmp_path,{}, {},offsets)


def test_incremental_audit_retains_an_incomplete_append(tmp_path,monkeypatch):
    import native_cycle_window as module
    seen = []
    monkeypatch.setattr(module,'verify_cycle',lambda physics,*args: seen.append(list(physics)))
    offsets = {}
    for name in ('physics_steps.jsonl','contact_steps.jsonl'):
        (tmp_path/name).write_text('{"sim_ns":1,"targets":{}}\n{"sim_ns":')
    (tmp_path/'native-events.jsonl').touch()
    module.audit_cycle(tmp_path,{}, {},offsets)
    for name in ('physics_steps.jsonl','contact_steps.jsonl'):
        with (tmp_path/name).open('a') as stream:
            stream.write('2,"targets":{}}\n')
    module.audit_cycle(tmp_path,{}, {},offsets)
    assert seen == [[1],[2]]
