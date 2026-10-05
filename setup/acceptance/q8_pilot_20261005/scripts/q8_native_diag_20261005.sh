#!/usr/bin/env bash
set -eo pipefail
source /home/ros/agentic_workcell_ws/setup/104_mainline_env.sh
command -v gdb || true
python3 - <<'PY'
import gz.transport13 as transport
print('transport_module=' + transport.__file__)
print('Node_methods=' + str([x for x in dir(transport.Node) if not x.startswith('_')]))
PY
dpkg-query -W 'libgz-transport13*' 'python3-gz-transport13*' 2>/dev/null || true
mkdir -p /tmp/q8_native_20261005
gcc -shared -fPIC -g -o /tmp/q8_native_20261005/abort_trace.so /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/pm-work/q8_abort_trace_20261005.c
python3 /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/pm-work/q8_worker_probe_20261005.py /home/ros/agentic_workcell_ws/setup/acceptance/q8_pilot_20261005/worker_probe_instrumented.json --native
