import json
import os
from pathlib import Path
import time
import urllib.request

from flexcell_skills.confidence_calibration import ConfidenceCalibration, prompt_digest
from flexcell_skills.contracts.backend_health import startup_health
from flexcell_skills.jev_backends import ClefBackend
from flexcell_skills.jev_policy import JevPolicy

cal = ConfidenceCalibration()
rows = []
for index in range(3):
    for label in ('legacy_two_second', 'configured_ten_second'):
        started = time.perf_counter_ns()
        backend = ClefBackend()
        ok, detail = backend.health() if label == 'legacy_two_second' else startup_health(backend, 'clef')
        rows.append(dict(index=index+1, probe=label, ok=ok, detail=detail,
                         elapsed_ms=(time.perf_counter_ns()-started)/1e6))
value = dict(record_kind='TCP_REACHABILITY_DIAGNOSTIC', results=rows,
             calibration_error=cal.error, calibration_sha256=cal.sha256, prompt_sha256=prompt_digest(),
             route_eligible=JevPolicy(ClefBackend()).route_eligible(.85),
             ros_domain_id=os.environ.get('ROS_DOMAIN_ID'),
             inference_timeout_s=os.environ['FLEXCELL_JEV_TIMEOUT_S'],
             startup_health_timeout_s=os.environ['FLEXCELL_JEV_HEALTH_TIMEOUT_S'],
             literal_tailnet_proxy_bypass=urllib.request.proxy_bypass('100.87.190.44'),
             robot_episodes=0, inference_calls=0,
             network_stability='NOT_ACCEPTED; DERP and earlier TCP failures retained',
             direct_connection_failure_root_cause='UNKNOWN; local UDP test alone does not identify the blocking peer/path')
with Path('/home/ros/fc_sync_logs/school_network_20261006/probe_attempt01.json').open('x') as f:
    json.dump(value,f,indent=2);f.write('\n')
print(json.dumps(value))
