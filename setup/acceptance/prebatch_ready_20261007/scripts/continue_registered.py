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


def main():
    COST.read_ledger(ROOT/'cost.jsonl');manifest=previous.load(ROOT/'plan/manifest.json');deployment=previous.load(ROOT/'plan/deployment.json')
    for rel,digest in dict(manifest['source_sha256'],**manifest['helpers_sha256']).items():COST.require(base.sha(WS/rel)==digest,'frozen source changed: '+rel)
    COST.require(base.sha(ROOT/'scripts/pilot.py')==manifest['executor_sha256'] and base.sha(ROOT/'scripts/invalid_control.py')==manifest['control_client_sha256'],'original executed driver/client changed')
    correction=previous.load(ROOT/'validation/control_audit_v2.json');COST.require(correction['guard_condition_confirmed'] and correction['zero_dispatch'] and correction['no_resubmission'],'retained control not confirmed')
    base.verify_deployment(deployment);execution=ROOT/'execution'
    COST.require(not (execution/'composite').exists() and not (execution/'S1').exists(),'registered target/source already attempted; do not repeat')
    (ROOT/'continuation').mkdir();started=time.perf_counter_ns()
    guard_result=previous.load(execution/'invalid-chain-control/client_result.json')
    def within_budget():COST.require(base.new_call_upper_bound(previous.load(ROOT/'plan/budget.json'),base.budget_snapshot())<250000,'registered paid stop threshold')
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
    base.write(ROOT/'execution_summary.json',dict(negative_control=guard_result,composite_result=previous.load(directory/'client_result.json'),source_result=source_result,native_episodes=2,control_requests=1,ledger_trial_records=3,original_driver_harness_failure='RETAINED',control_correction='POSTHOC_STATUS_CONSTANT; no resubmission',elapsed_minutes=(time.perf_counter_ns()-started)/60e9,no_replacement=True,n_ge_50='FROZEN',qualification='FROZEN'))
    print(json.dumps(dict(ok=True,native_episodes=2,control_requests=1,invalid_chain_zero_dispatch=True,source='SUCCEEDED')),flush=True)


if __name__=='__main__':main()
