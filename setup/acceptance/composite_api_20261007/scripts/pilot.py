#!/usr/bin/env python3
"""One prospectively bounded mainline composite + one source regression."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time

WS = Path('/home/ros/agentic_workcell_ws')
sys.path.insert(0, str(WS/'setup/transferbench'))
import t1_pilot as base
import t3_swap_pilot as previous

ROOT = Path(__file__).resolve().parents[1]
COST = base.COST


def audit_module():
    spec=importlib.util.spec_from_file_location('composite_audit',WS/'setup/127_composite_audit.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def register():
    if (ROOT/'cost.jsonl').exists():raise ValueError('registration already exists')
    deployment=previous.load(ROOT/'plan/deployment.json');base.verify_deployment(deployment)
    COST.require(deployment['policy']=='hybrid' and deployment['threshold']==.85,'expected hybrid .85')
    files=json.loads((ROOT/'validation/implementation_commit.json').read_text())['files']
    for rel in files:
        target=ROOT/'source'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(WS/rel,target)
    helpers={str(p.relative_to(WS)):base.sha(p) for p in [WS/'setup/125_transfer_cost.py',WS/'setup/transferbench/t1_pilot.py',WS/'setup/transferbench/t3_swap_pilot.py']}
    for rel in helpers:
        target=ROOT/'source'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(WS/rel,target)
    budget=base.budget_snapshot();COST.require(budget['limit_microyuan']==5_000_000,'budget limit must remain unchanged')
    base.write(ROOT/'plan/budget.json',budget)
    manifest=dict(record_kind='PROSPECTIVE_PLAN',protocol_id='mainline-composite-api-v1',baseline_revision='77e59e5e85769b5c5f0b5667b6e2e4028f57bc4a',
                  implementation_revision='ac9ca84f9b0eacd234747d76b90e8ed44b435fe3',runtime_fingerprint=deployment['runtime_fingerprint'],
                  policy='hybrid',threshold=.85,composite_attempts=1,source_regressions=1,max_native_components=3,max_native_episodes=4,
                  additional_paid_stop_threshold_cny=.25,no_failure_replacement=True,n_ge_50='FROZEN',qualification='FROZEN',
                  stop='unknown acceptance/terminal, signal, quarantine, missing identity or failed routing stops globally; known task failure stops its chain and permits only registered source regression',
                  success='typed parent success and action status 4; all three persisted native components and seven fresh observations pass independent auditor; source unchanged S1 predicate',
                  component_ids='internal in-process execution correlation, not separately accepted DDS RunPickPlace goals',
                  executor_sha256=base.sha(Path(__file__)),helpers_sha256=helpers,
                  source_sha256={rel:base.sha(WS/rel) for rel in files},
                  cost='shared API code and previous executor reuse are engineering work; partial agent elapsed only; human minutes and assistant tokens/fees NOT_RUN')
    base.write(ROOT/'plan/manifest.json',manifest)
    base.write(ROOT/'plan/success_predicate.json',dict(version=1,definition=manifest['success'],source_sha256=base.sha(WS/'setup/127_composite_audit.py')))
    base.write(ROOT/'plan/skill_contracts.json',dict(source_sha256=deployment['source_sha256'],installed_source_sha256=deployment['installed_source_sha256'],interface_sources_sha256=deployment['interface_sources_sha256']))
    artifacts={key:COST.pin(ROOT/'plan'/name) for key,name in [('task_manifest','manifest.json'),('initial_states','input.json'),
               ('success_predicate','success_predicate.json'),('skill_contracts','skill_contracts.json'),('baseline_config/hybrid','deployment.json'),('budget','budget.json')]}
    spec=dict(schema_version=1,record_kind='PROSPECTIVE_PLAN',protocol_id=manifest['protocol_id'],migration_axis='T3',arms=['hybrid'],
              cases=['buffer-B','relocate-A','return-B','S1-source-regression','orchestration-check'],baseline_revisions={'hybrid':manifest['baseline_revision']},
              qualification=dict(status='FROZEN',target_success_rate=.9),freeze_artifacts=artifacts)
    COST.initialize(ROOT/'cost.jsonl',spec)
    print(json.dumps(dict(status='REGISTERED',runtime_fingerprint=manifest['runtime_fingerprint'],max_native_episodes=4)),flush=True)


def run():
    COST.read_ledger(ROOT/'cost.jsonl')
    manifest=previous.load(ROOT/'plan/manifest.json');deployment=previous.load(ROOT/'plan/deployment.json')
    for rel,digest in dict(manifest['source_sha256'],**manifest['helpers_sha256']).items():
        COST.require(base.sha(WS/rel)==digest,'frozen code changed: '+rel)
    COST.require(base.sha(Path(__file__))==manifest['executor_sha256'],'pilot source changed')
    base.verify_deployment(deployment)
    armed=ROOT/'execution';armed.mkdir()  # Refuse a second attempt, including after interruption.
    start=time.perf_counter_ns();directory=armed/'composite';directory.mkdir()
    def within_budget():
        old=previous.load(ROOT/'plan/budget.json');current=base.budget_snapshot()
        COST.require(base.new_call_upper_bound(old,current)<250000,'registered paid stop threshold')
    within_budget()
    error=previous.prepare(directory,'hybrid','composite')
    if error:
        base.write(directory/'preparation_failure.json',dict(outcome='HARNESS_ERROR',error=error));raise ValueError(error)
    before=base.budget_snapshot();base.write(directory/'budget_before.json',before)
    offsets={p.name:p.stat().st_size for p in base.LOGS.glob('*.jsonl')};base.write(directory/'offsets.json',offsets)
    command=base.command(directory,'client',[sys.executable,str(previous.CLIENT),'--action','composite','--plan',str(ROOT/'plan/input.json'),'--timeout','360'],400)
    result=base.result_from_output(command['stdout']);base.write(directory/'client_result.json',result)
    after=base.budget_snapshot();base.write(directory/'budget_after.json',after)
    raw=directory/'raw';raw.mkdir()
    for path in base.LOGS.glob('*.jsonl'):
        COST.require(path.stat().st_size>=offsets.get(path.name,0),'runtime log truncated')
        (raw/path.name).write_bytes(path.read_bytes()[offsets.get(path.name,0):])
    unknown=False
    for path in raw.glob('*transport.jsonl'):
        for line in path.read_text().splitlines():
            if line.strip():
                event=COST.decode(line).get('event','')
                if 'quarantin' in event or event in ('goal_send_timeout','goal_response_unknown','goal_response_error'):unknown=True
    COST.require(result and command['return_code'] is not None and not base.signal_return_code(command['return_code'])
                 and command['return_code'] not in (4,) and result['action_status'] in (4,5,6) and not unknown,'unknown/signal/quarantined execution; stop')
    parent=Path(result['evidence_id']);COST.require(parent.is_file(),'parent receipt missing')
    shutil.copyfile(parent,directory/'parent.jsonl')
    records=[COST.decode(line) for line in parent.read_text().splitlines()]
    episodes=directory/'episodes';episodes.mkdir()
    components=[e['component'] for e in records if e['event']=='NATIVE_TERMINAL']
    for index,component in enumerate(components):
        episode_path=component.get('episode_path')
        COST.require(episode_path and Path(episode_path).is_file(),'native episode unconfirmed')
        path=Path(episode_path);shutil.copyfile(path,episodes/path.name);episode=previous.load(path)
        route=__import__('flexcell_skills.contracts.routing_audit',fromlist=['audit_routing_episode']).audit_routing_episode(episode,deployment)
        COST.require(route['ok'],'native routing failed')
        stage=component['stage_id'];summary=directory/(stage+'_summary.json')
        base.write(summary,dict(record_kind='ACTUAL_NATIVE_COMPONENT',stage_id=stage,parent_run_id=result['run_id'],
                               component=component,audit=route,raw_episode=COST.pin(episodes/path.name)))
        COST.append(ROOT/'cost.jsonl',dict(event_id='hybrid-'+stage+'-trial',kind='trial',arm='hybrid',trial_id=component['run_id'],purpose='adaptation',
                    case_id=stage,runtime_fingerprint=deployment['runtime_fingerprint'],calibration_sha256=deployment['active_backends']['fast']['calibration_sha256'],
                    reported_outcome='SUCCEEDED' if component['outcome']==0 else 'FAILED',return_code=command['return_code'],evidence=[COST.pin(summary)]))
        if index==0:
            previous.usage(ROOT,'hybrid',directory,episode,before,after,'adaptation')
        # Other components have their own usage directories; do not count slow API calls twice.
        if index:
            usage_dir=directory/(stage+'-usage');usage_dir.mkdir()
            previous.usage(ROOT,'hybrid',usage_dir,episode,after,after,'adaptation')
    if not components:
        summary=directory/'orchestration_failure.json';base.write(summary,dict(record_kind='HARNESS_ATTEMPT',result=result))
        COST.append(ROOT/'cost.jsonl',dict(event_id='hybrid-orchestration',kind='trial',arm='hybrid',trial_id=result['run_id'],purpose='adaptation',
                    case_id='orchestration-check',runtime_fingerprint=deployment['runtime_fingerprint'],calibration_sha256=deployment['active_backends']['fast']['calibration_sha256'],
                    reported_outcome='FAILED',return_code=command['return_code'],evidence=[COST.pin(summary)]))
    if result['outcome_val']==0:
        COST.require(result['action_status']==4,'success status mismatch')
        report=audit_module().audit(directory/'parent.jsonl',episodes,deployment);base.write(directory/'audit.json',report)
        print(json.dumps(dict(composite='SUCCEEDED',native_components=len(components),routing=report['routing'])),flush=True)
    else:
        base.write(directory/'audit.json',dict(ok=False,parent_outcome=result['outcome_val'],detail=result['detail'],receipt_retained=True))
        print(json.dumps(dict(composite='FAILED',native_components=len(components),detail=result['detail'])),flush=True)
    within_budget();source=armed/'source-preparation';source.mkdir()
    error=previous.prepare(source,'hybrid','S1')
    if error:
        base.write(source/'failure.json',dict(error=error));raise ValueError(error)
    source_result=previous.native(ROOT,'hybrid',armed/'S1',deployment,'S1-source-regression')
    COST.require(not source_result['harness_error'],'source harness failure')
    base.write(ROOT/'execution_summary.json',dict(composite_result=result,source_result=source_result,
               elapsed_minutes=(time.perf_counter_ns()-start)/60e9,max_native_episodes=4,no_resampling=True,n_ge_50='FROZEN'))
    print(json.dumps(dict(source=source_result['outcome'],elapsed_minutes=(time.perf_counter_ns()-start)/60e9)),flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['register']:register()
    elif sys.argv[1:]==['run']:run()
    else:raise SystemExit('usage: pilot.py register|run')
