"""Synthetic receipt checks; routing is stubbed, never live qualification."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest
from test_composite_checkpoint import paused, load, PLAN, FP
from flexcell_skills.contracts.composite import execute
from flexcell_skills.contracts.composite_checkpoint import claim_checkpoint
from flexcell_skills.contracts.episode import _sanitize


def fixture(tmp_path):
    rig,events,source,episodes=paused(tmp_path);checkpoint=load(source,episodes)
    rid='composite-'+'c'*16;checkpoint['claim']=claim_checkpoint(tmp_path,checkpoint,rid);rig.events=[]
    def native(stage,gid):
        c=rig.native(stage,gid);c['final_state'].update(parent_run_id=rid,stage_id=stage['stage_id'],execution_kind='IN_PROCESS_COMPONENT',component_execution_id=gid)
        p=episodes/(c['run_id']+'.json');c['episode_path']=str(p)
        e=dict(run_id=c['run_id'],runtime_fingerprint=FP,policy=dict(name='hybrid',version='1.1'),final_state=_sanitize(c['final_state']),
            steps=[dict(policy_input=dict(goal=dict(assignments=[[stage['object_name'],'task_place']])),policy_output=dict(action=a,target=stage['object_name']),executor_result=dict(outcome=0)) for a in ['PICK','PLACE','VERIFY']])
        p.write_text(json.dumps(e));return c
    assert execute(copy.deepcopy(PLAN),rig.observe,native,rig.emit,checkpoint=checkpoint)['outcome']==0
    rows=[dict(e,seq=i,record_kind='ACTUAL_COMPOSITE_TASK',run_id=rid,goal_uuid='d'*32,runtime_fingerprint=FP,policy='hybrid',policy_version='1.1',contract_version=2) for i,e in enumerate(rig.events)]
    resumed=tmp_path/(rid+'.jsonl');resumed.write_text(''.join(json.dumps(e)+'\n' for e in rows))
    spec=importlib.util.spec_from_file_location('resume_audit',Path(__file__).resolve().parents[4]/'setup/129_composite_resume_audit.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    m.audit_routing_episode=lambda *args:dict(ok=True)
    return m,source,resumed,episodes,dict(runtime_fingerprint=FP),tmp_path/(checkpoint['source_run_id']+'.resume-claim.json'),rows


def test_synthetic_complete_resume_audit(tmp_path):
    m,source,resumed,episodes,deployment,claim,rows=fixture(tmp_path)
    result=m.audit(source,resumed,episodes,deployment,claim)
    assert result['ok']


@pytest.mark.parametrize('mutation',[lambda r:r[0].update(pause_after_stages=False),lambda r:r[0].update(contract_version=True),lambda r:r[1]['checkpoint'].update(source_receipt_sha256='0'*64),lambda r:r.pop(2)])
def test_corrupt_resume_audit_refuses(tmp_path,mutation):
    m,source,resumed,episodes,deployment,claim,rows=fixture(tmp_path);mutation(rows)
    resumed.write_text(''.join(json.dumps(e)+'\n' for e in rows))
    with pytest.raises((ValueError,KeyError,IndexError)):
        m.audit(source,resumed,episodes,deployment,claim)
