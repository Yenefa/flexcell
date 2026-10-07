#!/usr/bin/env python3
"""Read-only development readiness. Qualification and n>=50 remain frozen."""
import argparse
import hashlib
import json
import os
import math
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/flexcell/flexcell_skills'))
from flexcell_skills.contracts.receipt_json import loads


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_deployment(deployment,workspace):
    excluded={'head','install','runtime_fingerprint'}
    expected=hashlib.sha256(json.dumps({k:v for k,v in deployment.items() if k not in excluded},sort_keys=True).encode()).hexdigest()
    if expected!=deployment['runtime_fingerprint']:raise ValueError('deployment fingerprint mismatch')
    for mapping in ['source_sha256','harness_sha256','interface_sources_sha256']:
        for rel,digest in deployment[mapping].items():
            if sha(workspace/rel)!=digest:raise ValueError('source drift: '+rel)
    src=workspace/'src/flexcell/flexcell_skills/flexcell_skills'
    if {str(p.relative_to(workspace)) for p in src.rglob('*.py')}!=set(deployment['source_sha256']):raise ValueError('source file-set drift')
    installed=Path(deployment['install'])/'flexcell_skills/lib/python3.12/site-packages/flexcell_skills'
    if {str(p.relative_to(installed)) for p in installed.rglob('*.py')}!=set(deployment['installed_source_sha256']):raise ValueError('installed file-set drift')
    for rel,digest in deployment['installed_source_sha256'].items():
        if sha(installed/rel)!=digest:raise ValueError('installed source drift: '+rel)
    for key,path in [('params_sha256',workspace/'src/flexcell/flexcell_skills/config/week1.yaml'),('world_sha256',Path(os.environ.get('FLEXCELL_WORLD',str(workspace/'worlds/flexcell_world'))+'.sdf'))]:
        if sha(path)!=deployment[key]:raise ValueError('configuration drift: '+key)
    profile=os.environ.get('FLEXCELL_DDS_PROFILE')
    if (sha(profile) if profile else None)!=deployment['dds_profile_sha256']:raise ValueError('DDS profile drift')
    return dict(ok=True,runtime_fingerprint=expected,source_files=len(deployment['source_sha256']),installed_files=len(deployment['installed_source_sha256']))


def verify_seal(root):
    items=loads((root/'SHA256SUMS.json').read_text())
    if type(items) is not dict:raise ValueError('current receipt map required')
    actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p.name!='SHA256SUMS.json' and '__pycache__' not in p.parts}
    if actual!=set(items):raise ValueError('receipt file set mismatch')
    for rel,entry in items.items():
        p=root/rel
        if p.resolve().is_relative_to(root.resolve()) is False:raise ValueError('receipt path escapes root')
        if p.stat().st_size!=entry['bytes'] or sha(p)!=entry['sha256']:raise ValueError('changed sealed receipt: '+rel)
    return dict(ok=True,files=len(items),manifest_sha256=sha(root/'SHA256SUMS.json'))


def confirmed_health(command):
    if type(command.get('return_code')) is not int or command['return_code']!=0:raise ValueError('health command failed/signal; reject any earlier success JSON')
    data=loads(command['stdout'])
    if type(data) is not dict or data.get('ok') is not True or data.get('busy') is not False or data.get('hard_fail')!=[]:raise ValueError('strict health not confirmed')
    if data['checks'].get('task_state')!='IDLE' or data['checks'].get('carry_engaged') is not False:raise ValueError('arm/carry not idle and released')
    return data


def live_probe(workspace,deployment):
    from flexcell_skills.confidence_calibration import ConfidenceCalibration,prompt_digest
    from flexcell_skills.jev_policy import JevPolicy
    from flexcell_skills.jev_backends import make_backend
    from flexcell_skills.contracts.backend_health import startup_health
    from flexcell_interfaces.action import RunComposite
    from flexcell_interfaces.srv import QueryCarry
    from rcl_interfaces.srv import GetParameters
    import rclpy
    from rclpy.action import ActionClient
    fast=deployment['active_backends']['fast'];c=ConfidenceCalibration();backend=make_backend('clef');p=JevPolicy(backend)
    if c.error or c.sha256!=fast['calibration_sha256'] or not p.route_eligible(deployment['threshold']):raise ValueError('active calibration gate invalid')
    for key,value in [('FLEXCELL_JEV_ENDPOINT',fast['endpoint']),('FLEXCELL_JEV_MODEL',fast['model']),('FLEXCELL_JEV_MODEL_SHA256',fast['model_sha256'])]:
        if os.environ.get(key)!=value:raise ValueError('active model identity drift: '+key)
    slow=deployment['active_backends']['slow']
    for key,value in [('FLEXCELL_LLM_ENDPOINT',slow['endpoint']),('FLEXCELL_LLM_MODEL',slow['model'])]:
        if os.environ.get(key)!=value:raise ValueError('active slow model drift: '+key)
    for key,want in [('FLEXCELL_JEV_TIMEOUT_S',deployment['policy_timeouts_s']['fast']),('FLEXCELL_LLM_TIMEOUT_S',deployment['policy_timeouts_s']['slow'])]:
        got=float(os.environ.get(key,'nan'))
        if not math.isfinite(got) or got!=want:raise ValueError('active timeout drift: '+key)
    health=float(os.environ.get('FLEXCELL_JEV_HEALTH_TIMEOUT_S','nan'))
    if not math.isfinite(health) or min(health,float(os.environ['FLEXCELL_JEV_TIMEOUT_S']))!=deployment['startup_health_timeout_s']:raise ValueError('health deadline drift')
    if int(os.environ.get('ROS_DOMAIN_ID','-1'))!=deployment['ros_domain_id'] or os.environ.get('RMW_IMPLEMENTATION')!=deployment['rmw_implementation']:raise ValueError('ROS environment drift')
    from urllib.parse import urlparse
    if urlparse(fast['endpoint']).hostname not in [v.strip() for v in os.environ.get('no_proxy','').split(',')]:raise ValueError('literal endpoint proxy bypass missing')
    started=time.perf_counter_ns();reachable,detail=startup_health(backend,'clef');elapsed=(time.perf_counter_ns()-started)/1e6
    if not reachable:return dict(ok=False,error=detail,tcp_probe_elapsed_ms=elapsed,tcp_reachable=False,inference_calls=0,native_episodes=0)
    rclpy.init();node=rclpy.create_node('flexcell_prebatch_readonly')
    try:
        action=ActionClient(node,RunComposite,'/run_composite')
        if not action.wait_for_server(timeout_sec=8):raise ValueError('RunComposite unavailable')
        params=node.create_client(GetParameters,'/task_fsm_server/get_parameters')
        if not params.wait_for_service(timeout_sec=5):raise ValueError('policy parameter service unavailable')
        pf=params.call_async(GetParameters.Request(names=['decision_policy','hybrid_threshold','jev_backend']))
        rclpy.spin_until_future_complete(node,pf,timeout_sec=5)
        if not pf.done() or pf.result() is None:raise ValueError('policy parameters unconfirmed')
        values=pf.result().values
        if len(values)!=3 or values[0].string_value!=deployment['policy'] or values[1].double_value!=deployment['threshold'] or values[2].string_value!='clef':raise ValueError('live policy/threshold/backend drift')
        client=node.create_client(QueryCarry,'/flexcell/carry_snapshot')
        if not client.wait_for_service(timeout_sec=5):raise ValueError('carry authority unavailable')
        future=client.call_async(QueryCarry.Request());rclpy.spin_until_future_complete(node,future,timeout_sec=5)
        if not future.done() or future.result() is None:raise ValueError('carry snapshot timed out')
        carry=future.result()
        if not carry.success or carry.state.engaged or carry.state.object_id:raise ValueError('carry authority not confirmed released')
        result=dict(ok=True,calibration_sha256=c.sha256,prompt_sha256=prompt_digest(),route_eligible=True,composite_action_available=True,carry_released=True,carry_revision=int(carry.revision),tcp_reachable=True,tcp_probe_elapsed_ms=elapsed,tcp_detail=detail,inference_calls=0,native_episodes=0)
    finally:node.destroy_node();rclpy.shutdown()
    started=time.perf_counter_ns()
    try:
        proc=subprocess.run([sys.executable,str(workspace/'setup/flexcell_admin.py'),'health'],capture_output=True,text=True,timeout=55)
        command=dict(return_code=proc.returncode,stdout=proc.stdout,stderr=proc.stderr,elapsed_ms=(time.perf_counter_ns()-started)/1e6)
    except subprocess.TimeoutExpired as exc:raise ValueError('strict health timed out; no success accepted') from exc
    result['strict_health_command']=command
    try:result['strict_health']=confirmed_health(command)
    except Exception as exc:result.update(ok=False,error=type(exc).__name__+': '+str(exc))
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--workspace',type=Path,default=Path('/home/ros/agentic_workcell_ws'))
    ap.add_argument('--deployment',required=True,type=Path);ap.add_argument('--receipt',type=Path,action='append',default=[])
    ap.add_argument('--live',action='store_true');ap.add_argument('--out',required=True,type=Path);args=ap.parse_args()
    report=dict(record_kind='PRE_BATCH_DEVELOPMENT_READINESS',schema_version=1,read_only_preflight_ok=False,ready_for_large_test=False,
                large_tests_started=False,qualification='FROZEN',AC90='NOT_RUN',n_ge_50='FROZEN',checks={},
                remaining_gates=['independent qualification split/sample size/confidence/budget not ratified','network stability NOT_ACCEPTED; DERP direct-path cause UNKNOWN','B-grasp limitation root cause UNKNOWN; do not hide FSM/Hybrid failures','complete human effort and actual GPU/API fees unmeasured'],dispatch_authorized=False)
    def check(name,fn):
        try:report['checks'][name]=fn()
        except Exception as exc:report['checks'][name]=dict(ok=False,error=type(exc).__name__+': '+str(exc))
    deployment=None
    try:deployment=loads(args.deployment.read_text())
    except Exception as exc:report['checks']['deployment']=dict(ok=False,error=str(exc))
    if deployment is not None:check('deployment',lambda:verify_deployment(deployment,args.workspace))
    for index,root in enumerate(args.receipt):check('seal-'+str(index),lambda root=root:verify_seal(root))
    if args.live and deployment is not None:check('live_readonly',lambda:live_probe(args.workspace,deployment))
    else:report['checks']['live_readonly']=dict(ok=False,status='NOT_RUN',reason='--live required for current readiness')
    report['read_only_preflight_ok']=all(c.get('ok') is True for c in report['checks'].values())
    encoded=json.dumps(report,indent=2,allow_nan=False)+'\n';args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('x') as f:f.write(encoded)
    print(encoded,end='');return 0 if report['read_only_preflight_ok'] else 2


if __name__=='__main__':raise SystemExit(main())
