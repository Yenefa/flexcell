import json
from pathlib import Path
import time

from flexcell_skills.jev_backends import ClefBackend

results = []
for index in range(5):
    started = time.perf_counter_ns()
    ok, detail = ClefBackend().health()
    results.append(dict(index=index+1, ok=ok, detail=detail,
                        elapsed_ms=(time.perf_counter_ns()-started)/1e6))
value = dict(record_kind='READ_ONLY_TCP_PROBE', results=results,
             inference_calls=0, new_robot_episodes=0,
             startup_warning='one TCP TimeoutError retained in hybrid/fleet.log',
             startup_root_cause='UNKNOWN; later observed GPU inference does not erase this warning')
with Path('/home/ros/fc_sync_logs/transferbench_t1_20261006/health_after_attempt01.json').open('x') as stream:
    json.dump(value, stream, indent=2)
    stream.write('\n')
print(json.dumps(value))
