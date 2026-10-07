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
    manifest=dict(record_kind='PROSPECTIVE_PLAN',protocol_id='mainline-prebatch-development-v1',baseline_revision='bf53df5e3339f9b55ed4a4b897c7e2e863e38952',
                  implementation_revision='f10be54fee2a4ae3dd1ef7479e155baee8fd4062',runtime_fingerprint=deployment['runtime_fingerprint'],
                  policy='hybrid',threshold=.85,composite_attempts=1,invalid_control_requests=1,source_regressions=1,max_native_components=1,max_native_episodes=2,
                  additional_paid_stop_threshold_cny=.25,no_failure_replacement=True,n_ge_50='FROZEN',qualification='FROZEN',
                  stop='unknown acceptance/terminal, signal, quarantine, missing identity or failed routing stops globally; known task failure stops its chain and permits only registered source regression',
                  success='invalid-chain typed60/status5 before any observation/native/model/controller work; one native composite passes independent audit; S1 frozen predicate passes',
                  component_ids='internal in-process execution correlation, not separately accepted DDS RunPickPlace goals',
                  executor_sha256=base.sha(Path(__file__)),helpers_sha256=helpers,
                  source_sha256={rel:base.sha(WS/rel) for rel in files},control_client_sha256=base.sha(ROOT/'scripts/invalid_control.py'),invalid_plan_sha256=base.sha(ROOT/'plan/invalid_chain.json'),
                  cost='shared API code and previous executor reuse are engineering work; partial agent elapsed only; human minutes and assistant tokens/fees NOT_RUN')
    base.write(ROOT/'plan/manifest.json',manifest)
    base.write(ROOT/'plan/success_predicate.json',dict(version=1,definition=manifest['success'],source_sha256=base.sha(WS/'setup/127_composite_audit.py')))
    base.write(ROOT/'plan/skill_contracts.json',dict(source_sha256=deployment['source_sha256'],installed_source_sha256=deployment['installed_source_sha256'],interface_sources_sha256=deployment['interface_sources_sha256']))
    artifacts={key:COST.pin(ROOT/'plan'/name) for key,name in [('task_manifest','manifest.json'),('initial_states','input.json'),
               ('success_predicate','success_predicate.json'),('skill_contracts','skill_contracts.json'),('baseline_config/hybrid','deployment.json'),('budget','budget.json')]}
    spec=dict(schema_version=1,record_kind='PROSPECTIVE_PLAN',protocol_id=manifest['protocol_id'],migration_axis='T3',arms=['hybrid'],
              cases=['single-A','S1-source-regression','invalid-chain-control'],baseline_revisions={'hybrid':manifest['baseline_revision']},
              qualification=dict(status='FROZEN',target_success_rate=.9),freeze_artifacts=artifacts)
    COST.initialize(ROOT/'cost.jsonl',spec)
    print(json.dumps(dict(status='REGISTERED',runtime_fingerprint=manifest['runtime_fingerprint'],max_native_episodes=2)),flush=True)


def run():
    COST.read_ledger(ROOT/'cost.jsonl');manifest=previous.load(ROOT/'plan/manifest.json');deployment=previous.load(ROOT/'plan/deployment.json')
    for rel,digest in dict(manifest['source_sha256'],**manifest['helpers_sha256']).items():COST.require(base.sha(WS/rel)==digest,'frozen source changed: '+rel)
    COST.require(base.sha(Path(__file__))==manifest['executor_sha256'] and base.sha(ROOT/'scripts/invalid_control.py')==manifest['control_client_sha256'] and base.sha(ROOT/'plan/invalid_chain.json')==manifest['invalid_plan_sha256'],'frozen control changed')
    base.verify_deployment(deployment);execution=ROOT/'execution';execution.mkdir();started=time.perf_counter_ns()
    def within_budget():COST.require(base.new_call_upper_bound(previous.load(ROOT/'plan/budget.json'),base.budget_snapshot())<250000,'registered paid stop threshold')
    within_budget();guard=execution/'invalid-chain-control';guard.mkdir();offsets={p.name:p.stat().st_size for p in base.LOGS.glob('*.jsonl')};episodes_before=set((base.LOGS/'episodes').glob('*.json'))
    command=base.command(guard,'client',[sys.executable,str(ROOT/'scripts/invalid_control.py'),str(ROOT/'plan/invalid_chain.json')],35)
    result=base.result_from_output(command['stdout']);guard_result=result;base.write(guard/'client_result.json',result)
    raw=guard/'raw';raw.mkdir()
    for p in base.LOGS.glob('*.jsonl'):
        COST.require(p.stat().st_size>=offsets.get(p.name,0),'log truncation')
        (raw/p.name).write_bytes(p.read_bytes()[offsets.get(p.name,0):])
    if result and result.get('evidence_id'):shutil.copyfile(result['evidence_id'],guard/'parent.jsonl')
    observed='FAILED' if result and result.get('outcome_val')==1 else 'HARNESS_ERROR'
    summary=guard/'summary.json';base.write(summary,dict(record_kind='ACTUAL_NEGATIVE_CONTROL',result=result,command_rc=command['return_code'],no_native_episode_expected=True,reported_outcome=observed))
    COST.append(ROOT/'cost.jsonl',dict(event_id='invalid-chain-control',kind='trial',arm='hybrid',trial_id=result['run_id'] if result else 'invalid-control-attempt',purpose='adaptation',case_id='invalid-chain-control',runtime_fingerprint=deployment['runtime_fingerprint'],calibration_sha256=deployment['active_backends']['fast']['calibration_sha256'],reported_outcome=observed,return_code=command['return_code'],evidence=[COST.pin(summary)]))
    watched=['decisions.jsonl','skill_transport.jsonl','controller_transport.jsonl','pick.jsonl','place.jsonl','verify.jsonl','observe.jsonl']
    unchanged=all((raw/name).stat().st_size==0 for name in watched if (raw/name).is_file())
    COST.require(command['return_code']==0 and result and result['outcome_val']==1 and result['error_code_val']==60 and result['action_status']==5 and not result['component_run_ids'] and unchanged and set((base.LOGS/'episodes').glob('*.json'))==episodes_before,'negative control not confirmed; stop without replacement')
    base.write(guard/'guard_audit.json',dict(ok=True,zero_policy_skill_controller_dispatch=True,zero_native_episodes=True,typed_error_code=60,negative_control_retained_as_failed_task_trial=True))
    within_budget();directory=execution/'composite';directory.mkdir();error=previous.prepare(directory,'hybrid','prebatch-single-A')
    if error:
        failure=directory/'preparation_failure.json';base.write(failure,dict(record_kind='HARNESS_ATTEMPT',attempt_id='prebatch-single-preparation',error=error));raise ValueError(error)
    before=base.budget_snapshot();base.write(directory/'budget_before.json',before);offsets={p.name:p.stat().st_size for p in base.LOGS.glob('*.jsonl')}
    command=base.command(directory,'client',[sys.executable,str(previous.CLIENT),'--action','composite','--plan',str(ROOT/'plan/input.json'),'--timeout','150'],180)
    result=base.result_from_output(command['stdout']);base.write(directory/'client_result.json',result);after=base.budget_snapshot();base.write(directory/'budget_after.json',after)
    raw=directory/'raw';raw.mkdir()
    for p in base.LOGS.glob('*.jsonl'):
        COST.require(p.stat().st_size>=offsets.get(p.name,0),'log truncation');(raw/p.name).write_bytes(p.read_bytes()[offsets.get(p.name,0):])
    COST.require(command['return_code'] is not None and not base.signal_return_code(command['return_code']) and result and result['action_status'] in (4,5,6),'unknown/signal composite; stop')
    parent=Path(result['evidence_id']);shutil.copyfile(parent,directory/'parent.jsonl');events=[COST.decode(x) for x in parent.read_text().splitlines()];components=[e['component'] for e in events if e['event']=='NATIVE_TERMINAL']
    eps=directory/'episodes';eps.mkdir()
    for c in components:
        p=Path(c['episode_path']);shutil.copyfile(p,eps/p.name);episode=previous.load(p)
        route=__import__('flexcell_skills.contracts.routing_audit',fromlist=['audit_routing_episode']).audit_routing_episode(episode,deployment)
        summary=directory/'native_summary.json';base.write(summary,dict(record_kind='ACTUAL_NATIVE_COMPONENT',component=c,audit=route,raw_episode=COST.pin(eps/p.name)))
        COST.append(ROOT/'cost.jsonl',dict(event_id='single-A-trial',kind='trial',arm='hybrid',trial_id=c['run_id'],purpose='adaptation',case_id='single-A',runtime_fingerprint=deployment['runtime_fingerprint'],calibration_sha256=deployment['active_backends']['fast']['calibration_sha256'],reported_outcome='SUCCEEDED' if c['outcome']==0 else 'FAILED',return_code=command['return_code'],evidence=[COST.pin(summary)]))
        previous.usage(ROOT,'hybrid',directory,episode,before,after,'adaptation');COST.require(route['ok'],'native routing')
    COST.require(result['outcome_val']==0 and result['action_status']==4 and len(components)==1,'composite functional regression failed; no replacement')
    report=audit_module().audit(directory/'parent.jsonl',eps,deployment);base.write(directory/'audit.json',report)
    within_budget();source=execution/'source-preparation';source.mkdir();error=previous.prepare(source,'hybrid','S1');COST.require(not error,'S1 preparation')
    source_result=previous.native(ROOT,'hybrid',execution/'S1',deployment,'S1-source-regression')
    COST.require(not source_result['harness_error'] and source_result['outcome']=='SUCCEEDED','S1 regression failed; no replacement')
    base.write(ROOT/'execution_summary.json',dict(negative_control=guard_result,composite_result=previous.load(directory/'client_result.json'),source_result=source_result,native_episodes=2,control_requests=1,ledger_trial_records=3,elapsed_minutes=(time.perf_counter_ns()-started)/60e9,no_replacement=True,n_ge_50='FROZEN',qualification='FROZEN'))
    print(json.dumps(dict(ok=True,native_episodes=2,control_requests=1,invalid_chain_zero_dispatch=True,source='SUCCEEDED')),flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['register']:register()
    elif sys.argv[1:]==['run']:run()
    else:raise SystemExit('usage: pilot.py register|run')
