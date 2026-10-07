"""Pre-dispatch contradictions and read-only checkpoint usability boundaries."""
import copy
import json
from pathlib import Path
import pytest
from test_composite import PLAN, Rig
from test_composite_checkpoint import paused,load,FP,SOURCE
from flexcell_skills.contracts.composite import execute
from flexcell_skills.contracts.composite_checkpoint import claim_checkpoint
from flexcell_skills.contracts.composite_prepare import checkpoint_report,plan_report
from flexcell_skills.contracts.receipt_json import loads


@pytest.mark.parametrize('change',[lambda p:p['stages'][1].update(destination=p['stages'][0]['destination'][:]),lambda p:p['final_empty_positions'].append(p['stages'][-1]['destination'][:])])
def test_impossible_late_condition_is_refused_before_any_motion(change):
    p=copy.deepcopy(PLAN);change(p);rig=Rig();r=execute(p,rig.observe,rig.native,rig.emit)
    assert r['error_code']==60 and not rig.calls and not rig.observed


def test_swap_dependency_precheck_is_not_execution():
    r=plan_report(PLAN);assert r['ok'] and not r['dispatch_authorized'] and r['stage_count']==3
    assert r['final_positions']['b']==PLAN['initial_objects']['a']


def test_available_inspection_creates_no_claim_or_episode(tmp_path):
    rig,events,path,episodes=paused(tmp_path);before={p:p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    r=checkpoint_report(tmp_path,SOURCE,FP,episodes)
    assert r['ok'] and r['resume_availability']=='AVAILABLE' and not r['dispatch_authorized']
    assert r['remaining_stage_ids']==['a','b'] and r['resume_fields']['resume_run_id']==SOURCE
    assert before=={p:p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}


def test_consumed_and_incomplete_claim_never_offer_resume(tmp_path):
    rig,events,path,episodes=paused(tmp_path);claim_checkpoint(tmp_path,load(path,episodes),'composite-'+'c'*16)
    r=checkpoint_report(tmp_path,SOURCE,FP,episodes)
    assert r['resume_availability']=='CONSUMED' and 'resume_fields' not in r
    claim=tmp_path/(SOURCE+'.resume-claim.json');claim.write_text('{')
    r=checkpoint_report(tmp_path,SOURCE,FP,episodes);assert not r['ok'] and r['resume_availability']=='INVALID'
    assert claim.read_text()=='{'


def test_unknown_tail_and_failed_terminal_cannot_authorize_resume(tmp_path):
    rig,events,path,episodes=paused(tmp_path);events.pop()
    path.write_text(''.join(json.dumps(e)+'\n' for e in events));r=checkpoint_report(tmp_path,SOURCE,FP,episodes)
    assert r['ok'] and r['resume_availability']=='UNKNOWN_TAIL' and not r['dispatch_authorized']
    events.append(dict(events[-1],seq=len(events),event='TERMINAL',outcome=1,error_code=62))
    path.write_text(''.join(json.dumps(e)+'\n' for e in events));r=checkpoint_report(tmp_path,SOURCE,FP,episodes)
    assert r['ok'] and r['resume_availability']=='NOT_PAUSED' and 'resume_fields' not in r


def test_inspection_rejects_current_runtime_drift(tmp_path):
    rig,events,path,episodes=paused(tmp_path);r=checkpoint_report(tmp_path,SOURCE,'2'*64,episodes)
    assert not r['ok'] and r['resume_availability']=='INVALID'


@pytest.mark.parametrize('field',['error_code','outcome'])
def test_persisted_boolean_terminal_is_not_equal_to_zero(tmp_path,field):
    rig,events,path,episodes=paused(tmp_path);p=next(episodes.glob('*.json'));e=json.loads(p.read_text())
    e['final_state'][field]=False;p.write_text(json.dumps(e))
    with pytest.raises(ValueError):load(path,episodes)


@pytest.mark.parametrize('text',['{"seq":0,"seq":1}','{"x":{"error_code":0,"error_code":false}}','{"x":NaN}','{"x":Infinity}','{"x":1e999}'])
def test_receipt_parser_rejects_ambiguous_or_nonfinite_values(text):
    with pytest.raises(ValueError):loads(text)
