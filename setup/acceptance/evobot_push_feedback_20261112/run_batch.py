#!/usr/bin/env python3
"""Host launcher: fixed six slots; abort infrastructure failure, retain task failures."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

repo = Path(__file__).resolve().parents[3]
artifacts = Path('/workspace/work/t08-feedback')
record = json.loads((Path(__file__).parent / 'preexecution_v2.json').read_text())
schedule = [('control', 'A1', 193), ('feedback', 'B1', 194), ('feedback', 'B2', 195),
            ('control', 'A2', 196), ('control', 'A3', 197), ('feedback', 'B3', 198)]
docker_env = {k:v for k,v in os.environ.items() if k not in
              ('DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH')}
status = dict(schedule=schedule, completed=[], status='STARTING', started_utc_ns=time.time_ns())
status_path = artifacts / 'batch_status.json'
assert not status_path.exists(), 'never overwrite a batch'


def save():
    status_path.write_text(json.dumps(status, indent=2))


save()
for arm, label, domain in schedule:
    for group in ('frozen_files', 'sources'):
        for name, digest in record[group].items():
            assert hashlib.sha256((repo/name).read_bytes()).hexdigest() == digest, name
    status.update(status='RUNNING', active=label)
    save()
    command = ['docker', '--host=unix:///var/run/docker.sock', 'exec', 'evobot-t08-feedback-20261112',
               '/opt/flexcell/repo/infra/entrypoint.sh', 'python3',
               '/candidate/setup/acceptance/evobot_push_feedback_20261112/run_case.py', arm, label, str(domain)]
    with (artifacts/(label+'.log')).open('x') as log:
        result = subprocess.run(command, env=docker_env, stdout=log, stderr=subprocess.STDOUT, timeout=600)
    run = artifacts/label
    valid = (result.returncode == 0 and (run/'verdict.json').is_file()
             and json.loads((run/'run_status.json').read_text())['status'] == 'EXECUTED')
    status['completed'].append(dict(label=label, returncode=result.returncode, infrastructure_valid=valid))
    if not valid:
        status.update(status='STOPPED_INFRASTRUCTURE_FAILURE', active=None)
        save()
        raise SystemExit(2)
    save()
status.update(status='COMPLETE', active=None, finished_utc_ns=time.time_ns())
save()
