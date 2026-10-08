#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash
source setup/104_mainline_env.sh
set -u
if [ "$ROS_DOMAIN_ID" != 45 ]; then exit 2; fi
python3 - <<'PY'
from pathlib import Path
import json,time
p=Path('/home/ros/fc_sync_logs/grasp_diagnostic_school_20261008/start_result.json')
assert not p.exists()
start=time.perf_counter_ns()
import subprocess
r=subprocess.run(['bash','setup/102_mainline_runtime.sh','cold','fsm','0.85'],capture_output=True,text=True,timeout=240)
p.write_text(json.dumps({'return_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'elapsed_ms':(time.perf_counter_ns()-start)/1e6},indent=2)+'\n')
print('START_RC',r.returncode)
raise SystemExit(r.returncode)
PY
