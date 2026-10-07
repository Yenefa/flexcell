#!/usr/bin/env bash
set -e
cd /home/ros/agentic_workcell_ws
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
test "$ROS_DOMAIN_ID" = 45
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PY'
from pathlib import Path
from datetime import datetime, timezone
import json
import shutil
import subprocess
import sys

ws=Path('/home/ros/agentic_workcell_ws')
root=ws/'setup/acceptance/local_fsm_20261008'
sys.path.insert(0,str(ws/'setup/transferbench'))
import bounded_runner as engine
import qualification_prepare as q
import t1_pilot as base
state=engine.status(root/'run',ws)
q.require(state['state']=='PAUSED' and state['completed_slots']==3
    and state['outcomes']==['SUCCEEDED']*3 and state['native_episode_count']==5,
    'actual local prefix not fully accepted; preserve stop instead of replacing trials')
deployment=sorted(base.RUNTIME.glob('*/deployment.json'))[-1]
report=root/'validation/readiness_postflight_report.json'
command=base.command(root/'validation','readiness_postflight_attempt01',
    [sys.executable,str(ws/'setup/131_prebatch_readiness.py'),'--live',
    '--workspace',str(ws),'--deployment',str(deployment),
    '--receipt',str(ws/'setup/acceptance/bounded_runner_20261007'),'--out',str(report)],85)
q.require(type(command['return_code']) is int and command['return_code']==0,
    'postflight unconfirmed or signaled')
data=q.loads(report.read_bytes())
q.require(data['read_only_preflight_ok'] is True
    and data['checks']['live_readonly']['active_policy']=='fsm'
    and data['checks']['live_readonly']['model_routes_required'] is False,
    'actual FSM idle/released state unconfirmed')
shutil.copy2(deployment.parent/'fleet.log',root/'validation/final_fleet.log')
active=Path('/home/ros/fc_sync_logs/local_fsm_active_20261008/run')
q.require(not active.exists(),'active destination already exists; never replace a collector')
active.parent.mkdir(parents=True,exist_ok=True)
before={str(p.relative_to(root/'run')):dict(bytes=p.stat().st_size,sha256=q.sha(p))
        for p in sorted((root/'run').rglob('*')) if p.is_file()}
(root/'run').rename(active)
for rel,pin in before.items():
    p=q.regular(active,rel)
    q.require(p.stat().st_size==pin['bytes'] and q.sha(p)==pin['sha256'],'collector changed during parking')
q.require(q.same_typed(engine.status(active,ws),state),'status changed during parking')
snapshot=root/'snapshot'
snapshot.mkdir(exist_ok=False)
shutil.copytree(active/'inputs',snapshot/'inputs')
shutil.copytree(active/'attempts',root/'execution')
shutil.copytree(active/'boundaries',snapshot/'boundaries')
engine.write(snapshot/'status.json',state)
for name in ['plan.json','events.jsonl']:
    shutil.copy2(active/name,snapshot/('registered_'+name))
engine.write(root/'validation/collector_handoff.json',dict(
    record_kind='PAUSED_COLLECTOR_HANDOFF',parked_utc=datetime.now(timezone.utc).isoformat(),
    historical_execution_root=str(root/'run'),active_root=str(active),
    file_pins=before,status=state,unchanged_bytes=True,
    remaining_native_episode_cap=5,remaining_logical_tasks=3,
    resume_requires_unchanged_code_model_calibration_and_real_hybrid_readiness=True,
    receipt_snapshot_only=True,qualification_sampling_authorized=False))
print(json.dumps({'state':state['state'],'native_episodes':5,'logical_tasks_succeeded':3,
    'active_root':str(active),'postflight_ok':True,'qualification_sampling_authorized':False}))
PY
