#!/usr/bin/env python3
"""Read-only pause/resume provenance audit, without merging native episodes."""
import argparse
import hashlib
import json
from pathlib import Path

from flexcell_skills.contracts.composite import matches, native_success, positions, vacant
from flexcell_skills.contracts.composite_checkpoint import validate_paused
from flexcell_skills.contracts.episode import _sanitize
from flexcell_skills.contracts.receipt_json import loads, same_typed
from flexcell_skills.contracts.routing_audit import audit_routing_episode


def require(value, detail):
    if not value:
        raise ValueError(detail)


def audit(paused_path, resumed_path, episode_directory, deployment, claim_path):
    paused_raw=Path(paused_path).read_bytes();paused=[loads(x) for x in paused_raw.decode().splitlines()]
    resumed=[loads(x) for x in Path(resumed_path).read_text().splitlines()]
    def episode(component):
        candidates=list(Path(episode_directory).glob('*_'+component['run_id']+'.json'))
        exact=Path(episode_directory)/(component['run_id']+'.json')
        if exact.is_file():candidates.append(exact)
        require(len(candidates)==1,'exactly one persisted native episode required')
        return loads(candidates[0].read_text())
    plan=paused[0]['plan'];fp=deployment['runtime_fingerprint']
    checkpoint=validate_paused(paused,plan,fp,episode)
    require(bool(resumed) and resumed[0]['event']=='PLAN' and resumed[0]['plan']==plan and resumed[0]['plan_sha256']==checkpoint['plan_sha256']
            and type(resumed[0]['pause_after_stages']) is int and resumed[0]['pause_after_stages']==0,'resumed plan mismatch')
    identity=['record_kind','run_id','goal_uuid','runtime_fingerprint','policy','policy_version','contract_version']
    for seq,row in enumerate(resumed):
        require(type(row['seq']) is int and row['seq']==seq and all(row[k]==resumed[0][k] for k in identity),'resume sequence/identity mismatch')
    require(type(resumed[0]['contract_version']) is int and resumed[0]['contract_version']==2 and resumed[0]['runtime_fingerprint']==fp
            and resumed[0]['policy']==checkpoint['policy'] and resumed[0]['policy_version']==checkpoint['policy_version'],'resume runtime/policy mismatch')
    require(resumed[1]['event']=='RESUME','resume provenance missing')
    inherited=resumed[1]['checkpoint'];claim=loads(Path(claim_path).read_text())
    for name,value in checkpoint.items():require(inherited.get(name)==value,'checkpoint mismatch: '+name)
    source_sha=hashlib.sha256(paused_raw).hexdigest()
    require(inherited['source_receipt_sha256']==source_sha and inherited['claim']==claim
            and claim==dict(record_kind='COMPOSITE_RESUME_CLAIM',source_run_id=checkpoint['source_run_id'],source_receipt_sha256=source_sha,
                            resumed_run_id=resumed[0]['run_id']),'claim/receipt hash mismatch')
    expected=dict(checkpoint['expected_positions']);stage_ids=checkpoint['completed_stage_ids'][:]
    runs=checkpoint['component_run_ids'][:];goals=checkpoint['component_goal_uuids'][:]
    components=[e['component'] for e in paused if e['event']=='NATIVE_TERMINAL'];cursor=2
    tolerance,clearance=plan['position_tolerance_m'],plan['clearance_m']
    for stage in plan['stages'][len(stage_ids):]:
        segment=resumed[cursor:cursor+5];sid=stage['stage_id']
        require([e['event'] for e in segment]==['OBSERVATION','STARTED','NATIVE_TERMINAL','OBSERVATION','COMMITTED']
                and all(e['stage_id']==sid for e in segment),'resumed stage sequence mismatch')
        pre,start,native,post,committed=segment
        require(pre['boundary']=='before' and post['boundary']=='after','fresh boundary missing')
        actual=positions(pre['observation'],expected)
        require(matches(actual,expected,tolerance) and vacant(actual,stage['destination'],clearance,stage['object_name']),'resumed precondition failed')
        c=native['component'];goal_id=start['component_goal_uuid'];require(native_success(c,goal_id,tolerance),'resumed native terminal unconfirmed')
        e=episode(c);final=e['final_state']
        require(e['run_id']==c['run_id'] and e['runtime_fingerprint']==fp and same_typed(final,_sanitize(c['final_state']))
                and final['parent_run_id']==resumed[0]['run_id'] and final['stage_id']==sid
                and final['execution_kind']=='IN_PROCESS_COMPONENT' and final['component_execution_id']==goal_id,'resumed native identity mismatch')
        require(all(s['policy_input']['goal']['assignments']==[[stage['object_name'],'task_place']] for s in e['steps']),'native target mismatch')
        for action in ['PICK','PLACE','VERIFY']:
            require(any(s['policy_output']['action']==action and s['policy_output']['target']==stage['object_name']
                        and type((s.get('executor_result') or {}).get('outcome')) is int and s['executor_result']['outcome']==0 for s in e['steps']),'native action missing: '+action)
        expected[stage['object_name']]=list(stage['destination'])
        require(matches(positions(post['observation'],expected),expected,tolerance) and committed['expected_positions']==expected
                and committed['component_run_id']==c['run_id'],'resumed commit mismatch')
        components.append(c);stage_ids.append(sid);runs.append(c['run_id']);goals.append(goal_id);cursor+=5
    require(cursor==len(resumed)-2 and len(set(runs))==len(runs) and len(set(goals))==len(goals),'repeated native ID or unexpected tail')
    last,terminal=resumed[-2:]
    require(last['event']=='OBSERVATION' and last['boundary']=='final' and last['stage_id']=='','final joint measurement missing')
    actual=positions(last['observation'],expected)
    require(matches(actual,expected,tolerance) and all(vacant(actual,p,clearance) for p in plan['final_empty_positions']),'final joint predicate failed')
    require(terminal['event']=='TERMINAL' and type(terminal['outcome']) is int and terminal['outcome']==0
            and type(terminal['error_code']) is int and terminal['error_code']==0
            and terminal['completed_stage_ids']==stage_ids and terminal['component_run_ids']==runs and terminal['component_goal_uuids']==goals,'resumed terminal mismatch')
    routes=[audit_routing_episode(episode(c),deployment) for c in components]
    require(all(r['ok'] for r in routes),'native routing failed')
    return dict(ok=True,record_kind='ACTUAL_COMPOSITE_RESUME_AUDIT',paused_run_id=checkpoint['source_run_id'],resumed_run_id=resumed[0]['run_id'],
                runtime_fingerprint=fp,inherited_stages=len(checkpoint['completed_stage_ids']),new_stages=len(stage_ids)-len(checkpoint['completed_stage_ids']),
                component_run_ids=runs,routing=routes,final_positions=actual,no_replayed_stage=True,
                qualification='FROZEN',physical_safety='NOT_RUN')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ['paused','resumed','episodes','deployment','claim']:ap.add_argument('--'+name,required=True,type=Path)
    args=ap.parse_args()
    try:result=audit(args.paused,args.resumed,args.episodes,loads(args.deployment.read_text()),args.claim)
    except Exception as exc:
        print(json.dumps(dict(ok=False,error=type(exc).__name__+': '+str(exc))));return 1
    print(json.dumps(result,indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
