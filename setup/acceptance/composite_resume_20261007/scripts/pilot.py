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
    spec=importlib.util.spec_from_file_location('composite_audit',WS/'setup/129_composite_resume_audit.py')
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
    manifest=dict(record_kind='PROSPECTIVE_PLAN',protocol_id='mainline-composite-resume-v2',baseline_revision='d14c7954049a2eeb799f18e76afe29b706cf992b',
                  implementation_revision='6624bb7b60bf2895593da5083f2153214afcec9d',runtime_fingerprint=deployment['runtime_fingerprint'],
                  policy='hybrid',threshold=.85,composite_attempts=1,pause_after_stages=1,resume_attempts=1,duplicate_guard_attempts=1,source_regressions=1,max_native_components=3,max_native_episodes=4,
                  additional_paid_stop_threshold_cny=.25,no_failure_replacement=True,n_ge_50='FROZEN',qualification='FROZEN',
                  stop='unknown acceptance/terminal, signal, quarantine, missing identity or failed routing stops globally; known task failure stops its chain and permits only registered source regression',
                  success='pause typed3/status4; same-fingerprint owned fleet restart; resume typed0/status4; exactly three unique native components and no replay; duplicate typed65 and no dispatch; source unchanged S1 predicate',
                  component_ids='internal in-process execution correlation, not separately accepted DDS RunPickPlace goals',
                  executor_sha256=base.sha(Path(__file__)),helpers_sha256=helpers,
                  source_sha256={rel:base.sha(WS/rel) for rel in files},
                  cost='shared API code and previous executor reuse are engineering work; partial agent elapsed only; human minutes and assistant tokens/fees NOT_RUN')
    base.write(ROOT/'plan/manifest.json',manifest)
    base.write(ROOT/'plan/success_predicate.json',dict(version=1,definition=manifest['success'],source_sha256=base.sha(WS/'setup/129_composite_resume_audit.py')))
    base.write(ROOT/'plan/skill_contracts.json',dict(source_sha256=deployment['source_sha256'],installed_source_sha256=deployment['installed_source_sha256'],interface_sources_sha256=deployment['interface_sources_sha256']))
    artifacts={key:COST.pin(ROOT/'plan'/name) for key,name in [('task_manifest','manifest.json'),('initial_states','input.json'),
               ('success_predicate','success_predicate.json'),('skill_contracts','skill_contracts.json'),('baseline_config/hybrid','deployment.json'),('budget','budget.json')]}
    spec=dict(schema_version=1,record_kind='PROSPECTIVE_PLAN',protocol_id=manifest['protocol_id'],migration_axis='T3',arms=['hybrid'],
              cases=['buffer-B','relocate-A','return-B','S1-source-regression','orchestration-check'],baseline_revisions={'hybrid':manifest['baseline_revision']},
              qualification=dict(status='FROZEN',target_success_rate=.9),freeze_artifacts=artifacts)
    COST.initialize(ROOT/'cost.jsonl',spec)
    print(json.dumps(dict(status='REGISTERED',runtime_fingerprint=manifest['runtime_fingerprint'],max_native_episodes=4)),flush=True)


def run():
    COST.read_ledger(ROOT/'cost.jsonl');manifest=previous.load(ROOT/'plan/manifest.json');deployment=previous.load(ROOT/'plan/deployment.json')
    for rel,digest in dict(manifest['source_sha256'],**manifest['helpers_sha256']).items():
        COST.require(base.sha(WS/rel)==digest,'frozen code changed: '+rel)
    COST.require(base.sha(Path(__file__))==manifest['executor_sha256'],'pilot changed')
    base.verify_deployment(deployment);armed=ROOT/'execution';armed.mkdir()
    start=time.perf_counter_ns();directory=armed/'composite';directory.mkdir()
    def within_budget():
        COST.require(base.new_call_upper_bound(previous.load(ROOT/'plan/budget.json'),base.budget_snapshot())<250000,'paid stop threshold')
    within_budget();error=previous.prepare(directory,'hybrid','composite');COST.require(not error,'initial preparation: '+str(error))
    before=base.budget_snapshot();base.write(directory/'budget_before.json',before)
    offsets={p.name:p.stat().st_size for p in base.LOGS.glob('*.jsonl')};base.write(directory/'offsets.json',offsets)
    cli=[sys.executable,str(previous.CLIENT),'--action','composite','--plan',str(ROOT/'plan/input.json'),'--timeout','360']
    def call(name,extra):
        command=base.command(directory,name,cli+extra,400);result=base.result_from_output(command['stdout']);base.write(directory/(name+'_result.json'),result)
        COST.require(result and command['return_code'] is not None and not base.signal_return_code(command['return_code']) and command['return_code']!=4,'unknown/signal client')
        parent=Path(result['evidence_id']);COST.require(parent.is_file(),'parent missing');shutil.copyfile(parent,directory/(name+'_parent.jsonl'))
        return command,result,parent
    pcommand,paused,parent=call('pause',['--pause-after-stages','1'])
    COST.require(paused['outcome_val']==3 and paused['action_status']==4,'requested pause not confirmed; no replacement')
    within_budget()
    restart=base.command(directory,'restart',['bash',str(WS/'setup/102_mainline_runtime.sh'),'switch','hybrid','.85'],100)
    COST.require(restart['return_code']==0,'restart readiness failed; do not resume')
    deployments=sorted((Path.home()/'.local/share/flexcell/mainline/runtime').glob('*/deployment.json'))
    fresh=previous.load(deployments[-1]);base.write(directory/'deployment_after_restart.json',fresh)
    COST.require(fresh['runtime_fingerprint']==deployment['runtime_fingerprint'],'restart fingerprint changed')
    fleet=deployments[-1].parent/'fleet.log';shutil.copyfile(fleet,directory/'restart_fleet.log')
    COST.require("jev backend 'clef' unavailable" not in fleet.read_text(),'clef startup unavailable')
    extra=['--resume-run-id',paused['run_id'],'--resume-receipt-sha256',base.sha(parent)]
    rcommand,resumed,rparent=call('resume',extra)
    COST.require(resumed['outcome_val']==0 and resumed['action_status']==4,'resume failed; no replacement')
    after=base.budget_snapshot();base.write(directory/'budget_after.json',after)
    raw=directory/'raw';raw.mkdir()
    for path in base.LOGS.glob('*.jsonl'):
        COST.require(path.stat().st_size>=offsets.get(path.name,0),'runtime log truncated')
        (raw/path.name).write_bytes(path.read_bytes()[offsets.get(path.name,0):])
    for path in raw.glob('*transport.jsonl'):
        for line in path.read_text().splitlines():
            event=COST.decode(line).get('event','')
            COST.require('quarantin' not in event and event not in ('goal_send_timeout','goal_response_unknown','goal_response_error'),'unknown transport stops')
    records=[COST.decode(x) for p in [parent,rparent] for x in p.read_text().splitlines()]
    components=[e['component'] for e in records if e['event']=='NATIVE_TERMINAL'];COST.require(len(components)==3,'expected native count')
    episodes=directory/'episodes';episodes.mkdir()
    for index,c in enumerate(components):
        ep=Path(c['episode_path']);shutil.copyfile(ep,episodes/ep.name);episode=previous.load(ep)
        route=__import__('flexcell_skills.contracts.routing_audit',fromlist=['audit_routing_episode']).audit_routing_episode(episode,deployment);COST.require(route['ok'],'native route failed')
        summary=directory/(c['stage_id']+'_summary.json');base.write(summary,dict(record_kind='ACTUAL_NATIVE_COMPONENT',component=c,audit=route,raw_episode=COST.pin(episodes/ep.name)))
        COST.append(ROOT/'cost.jsonl',dict(event_id='hybrid-'+c['stage_id']+'-trial',kind='trial',arm='hybrid',trial_id=c['run_id'],purpose='adaptation',case_id=c['stage_id'],runtime_fingerprint=deployment['runtime_fingerprint'],calibration_sha256=deployment['active_backends']['fast']['calibration_sha256'],reported_outcome='SUCCEEDED' if c['outcome']==0 else 'FAILED',return_code=rcommand['return_code'],evidence=[COST.pin(summary)]))
        usage=directory/(c['stage_id']+'-usage');usage.mkdir();previous.usage(ROOT,'hybrid',usage,episode,before if index==0 else after,after,'adaptation')
    claim=parent.parent/(paused['run_id']+'.resume-claim.json');shutil.copyfile(claim,directory/'claim.json')
    report=audit_module().audit(directory/'pause_parent.jsonl',directory/'resume_parent.jsonl',episodes,deployment,directory/'claim.json');base.write(directory/'audit.json',report)
    logs_before={p.name:p.stat().st_size for p in base.LOGS.glob('*.jsonl')}
    dcommand,duplicate,dparent=call('duplicate',extra)
    COST.require(duplicate['outcome_val']==1 and duplicate['error_code']=='ERR_RESUME_REJECTED','duplicate not refused')
    # Rejection may add a parent/demo receipt; skill, policy and controller logs must not move.
    guarded=['decisions.jsonl','skill_transport.jsonl','controller_transport.jsonl','pick.jsonl','place.jsonl','verify.jsonl','observe.jsonl']
    COST.require(all((base.LOGS/name).stat().st_size==logs_before[name] for name in guarded if name in logs_before),'duplicate dispatched work')
    base.write(directory/'duplicate_guard.json',dict(ok=True,error_code=65,zero_dispatch=True,log_offsets=logs_before))
    within_budget();source=armed/'source-preparation';source.mkdir();error=previous.prepare(source,'hybrid','S1');COST.require(not error,'source preparation')
    source_result=previous.native(ROOT,'hybrid',armed/'S1',deployment,'S1-source-regression');COST.require(not source_result['harness_error'],'source harness failure')
    base.write(ROOT/'execution_summary.json',dict(paused=paused,resumed=resumed,duplicate=duplicate,source_result=source_result,elapsed_minutes=(time.perf_counter_ns()-start)/60e9,max_native_episodes=4,no_resampling=True,n_ge_50='FROZEN'))
    print(json.dumps(dict(resume='SUCCEEDED',no_replay=True,source=source_result['outcome'])),flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['register']:register()
    elif sys.argv[1:]==['run']:run()
    else:raise SystemExit('usage: pilot.py register|run')
