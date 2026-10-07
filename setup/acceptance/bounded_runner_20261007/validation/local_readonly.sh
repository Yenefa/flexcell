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
import concurrent.futures
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

root = Path('/home/ros/agentic_workcell_ws/setup/acceptance/bounded_runner_20261007')
ws = Path('/home/ros/agentic_workcell_ws')

def health():
    start = time.perf_counter_ns()
    try:
        proc = subprocess.run(['python3', str(ws / 'setup/flexcell_admin.py'), 'health'],
                              capture_output=True, text=True, timeout=65)
        return dict(return_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr,
                    elapsed_ms=(time.perf_counter_ns() - start) / 1e6)
    except subprocess.TimeoutExpired:
        return dict(return_code=None, error='TIMEOUT',
                    elapsed_ms=(time.perf_counter_ns() - start) / 1e6)

def peer():
    cli = '/mnt/c/Program Files/Tailscale/tailscale.exe'
    proc = subprocess.run([cli, 'status', '--json'], capture_output=True, text=True, timeout=15)
    value = dict(return_code=proc.returncode)
    if proc.returncode == 0:
        raw = json.loads(proc.stdout)
        value.update(backend_state=raw.get('BackendState'), self_online=raw.get('Self', {}).get('Online'),
            peer=[{k: p.get(k) for k in ['HostName', 'TailscaleIPs', 'Online', 'LastSeen', 'CurAddr', 'Relay']}
                  for p in raw.get('Peer', {}).values() if '100.87.190.44' in p.get('TailscaleIPs', [])])
    ping = subprocess.run([cli, 'ping', '--c', '1', '--timeout', '5s', '100.87.190.44'],
                          capture_output=True, text=True, timeout=15)
    value['ping'] = dict(return_code=ping.returncode, stdout=ping.stdout, stderr=ping.stderr)
    return value

started = datetime.now(timezone.utc).isoformat()
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    health_future = executor.submit(health)
    peer_future = executor.submit(peer)
    local_health = health_future.result()
    network = peer_future.result()
result = dict(record_kind='POST_STOP_READ_ONLY_DIAGNOSTIC', started_utc=started,
    finished_utc=datetime.now(timezone.utc).isoformat(), local_health=local_health, network=network,
    ros_domain_id=os.environ['ROS_DOMAIN_ID'], rmw_implementation=os.environ['RMW_IMPLEMENTATION'],
    literal_endpoint_proxy_bypass=urllib.request.proxy_bypass('100.87.190.44'),
    native_episodes_dispatched=0, inference_calls=0, qualification_sampling_authorized=False)
output = root / 'validation/local_readonly_attempt01.json'
with output.open('x') as stream:
    json.dump(result, stream, indent=2, allow_nan=False)
    stream.write('\n')
print(json.dumps(result, indent=2, allow_nan=False))
PY
