"""Offline composite plan/checkpoint inspection, without dispatching any goal."""
import hashlib
from pathlib import Path
import re

from flexcell_skills.contracts.composite import CompositeError, prepare_plan
from flexcell_skills.contracts.composite_checkpoint import load_checkpoint, plan_digest
from flexcell_skills.contracts.receipt_json import loads


def plan_report(plan):
    plan=prepare_plan(plan);expected={k:v[:] for k,v in plan['initial_objects'].items()}
    for stage in plan['stages']:expected[stage['object_name']]=stage['destination'][:]
    return dict(ok=True,record_kind='COMPOSITE_PLAN_PRECHECK',plan_sha256=plan_digest(plan),stage_count=len(plan['stages']),
                final_positions=expected,scope='declared center positions; no IK, motion or fresh observation',dispatch_authorized=False)


def checkpoint_report(directory,run_id,fingerprint,episode_directory):
    report=dict(ok=False,record_kind='COMPOSITE_CHECKPOINT_INSPECTION',run_id=run_id,
                resume_availability='INVALID',dispatch_authorized=False)
    try:
        if type(run_id) is not str or not re.fullmatch('composite-[0-9a-f]{16}',run_id):raise ValueError('invalid run ID')
        path=Path(directory).expanduser().resolve()/(run_id+'.jsonl')
        if not path.is_file() or path.is_symlink():raise ValueError('server-owned journal missing')
        raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest();events=[loads(x) for x in raw.decode().splitlines()]
        if not events or not all(type(e) is dict for e in events):raise ValueError('empty/invalid journal')
        first=events[0];identity=['record_kind','run_id','goal_uuid','runtime_fingerprint','policy','policy_version','contract_version']
        for seq,event in enumerate(events):
            if type(event.get('seq')) is not int or event['seq']!=seq or any(k not in first or event.get(k)!=first[k] for k in identity):raise ValueError('journal identity/sequence mismatch')
        if first['run_id']!=run_id or first['record_kind']!='ACTUAL_COMPOSITE_TASK':raise ValueError('journal origin mismatch')
        report.update(receipt_sha256=digest,receipt_path=str(path),recorded_runtime_fingerprint=first['runtime_fingerprint'])
        terminal=events[-1]
        if terminal.get('event')!='TERMINAL':
            report.update(ok=True,resume_availability='UNKNOWN_TAIL',reason='no confirmed terminal; inspection cannot authorize replay');return report
        if any(e.get('event')=='TERMINAL' for e in events[:-1]):raise ValueError('multiple terminal records')
        outcome,code=terminal.get('outcome'),terminal.get('error_code')
        if type(outcome) is not int or outcome not in (0,1,2,3) or type(code) is not int or code<0:raise ValueError('invalid typed terminal')
        report.update(reported_outcome=outcome,reported_error_code=code)
        if outcome!=3:
            report.update(ok=True,resume_availability='NOT_PAUSED',completion_verified=False);return report
        plan=prepare_plan(first['plan']);checkpoint=load_checkpoint(directory,run_id,digest,plan,fingerprint,episode_directory)
        claim=path.parent/(run_id+'.resume-claim.json')
        report.update(ok=True,completed_stage_ids=checkpoint['completed_stage_ids'],remaining_stage_ids=[s['stage_id'] for s in plan['stages'][len(checkpoint['completed_stage_ids']):]],checkpoint_valid=True)
        if claim.exists() or claim.is_symlink():
            if not claim.is_file() or claim.is_symlink():raise ValueError('invalid existing claim; never remove it')
            data=loads(claim.read_text())
            if type(data) is not dict or set(data)!={'record_kind','source_run_id','source_receipt_sha256','resumed_run_id'} or data['record_kind']!='COMPOSITE_RESUME_CLAIM' or data['source_run_id']!=run_id or data['source_receipt_sha256']!=digest or type(data['resumed_run_id']) is not str or not re.fullmatch('composite-[0-9a-f]{16}',data['resumed_run_id']):raise ValueError('claim identity mismatch; never remove it')
            report.update(resume_availability='CONSUMED',claimed_by_run_id=data['resumed_run_id'])
        else:
            report.update(resume_availability='AVAILABLE',resume_fields=dict(resume_run_id=run_id,resume_receipt_sha256=digest),fresh_state_check='REQUIRED_AT_DISPATCH')
        return report
    except (CompositeError,ValueError,KeyError,TypeError,OSError) as exc:
        report.update(ok=False,resume_availability='INVALID',reason=type(exc).__name__+': '+str(exc));return report
