#!/usr/bin/env python3
"""Run the two fixed geometry-pilot slots serially in the owned container."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

repo = Path(__file__).resolve().parents[3]
out = Path('/workspace/work/t08-architecture')
pre = json.loads((Path(__file__).parent/'preexecution.json').read_text())
status = dict(started_utc_ns=time.time_ns(), status='STARTING', completed=[])
path = out/'pair_status.json'
assert not path.exists(), 'never overwrite an executed pair'
environment = {k:v for k,v in os.environ.items() if k not in
               ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH')}
for slot in pre['schedule']:
    for group in ('sources','frozen_files'):
        for name,digest in pre[group].items():
            assert hashlib.sha256((repo/name).read_bytes()).hexdigest()==digest,name
    label = slot['label']
    status.update(status='RUNNING', active=label)
    path.write_text(json.dumps(status,indent=2))
    command = ['docker','--host=unix:///var/run/docker.sock','exec','evobot-t08-architecture-20261112',
               '/opt/flexcell/repo/infra/entrypoint.sh','python3',
               '/candidate/setup/acceptance/evobot_contact_arch_audit_20261112/run_case.py',
               'feedback',label,str(slot['domain']),str(slot['ee_height_m']),slot['profile']]
    with (out/(label+'.log')).open('x') as stream:
        result = subprocess.run(command,env=environment,stdout=stream,stderr=subprocess.STDOUT,timeout=600)
    valid = result.returncode==0 and (out/label/'verdict.json').exists()
    status['completed'].append(dict(label=label,infrastructure_valid=valid,returncode=result.returncode))
    if not valid:
        status.update(status='STOPPED_INFRASTRUCTURE_FAILURE',active=None)
        path.write_text(json.dumps(status,indent=2))
        raise SystemExit(2)
status.update(status='COMPLETE',active=None,finished_utc_ns=time.time_ns())
path.write_text(json.dumps(status,indent=2))
