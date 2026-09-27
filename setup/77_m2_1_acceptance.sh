#!/usr/bin/env bash
# 77_m2_1_acceptance.sh — M2.1 WorldState v2 runtime acceptance
# start -> health -> reset -> happy demo (parity vs att3 baseline) -> live
# canonical envelope probe -> stop. Evidence -> acceptance/week15/m2_1_worldstate_v2/
source /opt/ros/jazzy/setup.bash
cd /home/ros/agentic_workcell_ws

E=/mnt/f/flexcell-stage/setup/acceptance/week15/m2_1_worldstate_v2
D=/mnt/f/flexcell-stage/setup/acceptance/week15/delivery_20260926
CLI=/tmp/flexcell_cli
mkdir -p "$E"

tr -d "\r" < /mnt/f/flexcell-stage/setup/flexcell > "$CLI"

echo "== 1. managed start =="
{ echo "=== flexcell start | $(date -Is) ==="; t0=$(date +%s); bash "$CLI" start; rc=$?; t1=$(date +%s); echo "START_DURATION_S=$((t1-t0))"; echo "RC=$rc"; } > "$E/77_start.out" 2>&1
grep -E "START OK|START FAILED|START_DURATION_S" "$E/77_start.out"

echo "== 2. health gate =="
{ echo "=== flexcell health (strict) | $(date -Is) ==="; bash "$CLI" health; echo "RC=$?"; } > "$E/77_health.out" 2>&1
grep -c '"OK"' "$E/77_health.out" | xargs echo "OK checks:"

echo "== 3. canonical reset =="
{ echo "=== flexcell reset | $(date -Is) ==="; bash "$CLI" reset; echo "RC=$?"; } > "$E/77_reset.out" 2>&1
grep -o '"ok": [a-z]*' "$E/77_reset.out" | tail -1

echo "== 4. happy demo (week1_demo_v1) =="
{
  echo "=== happy demo | $(date -Is) ==="
  timeout 170 python3 src/flexcell/flexcell_skills/test/w1_client.py --action demo --scenario week1_demo_v1
  echo "RC=$?"
} > "$E/77_demo.out" 2>&1
grep -E '"outcome"|zone_a_error_m|zone_b_error_m|run_id' "$E/77_demo.out" | head -6
tail -n 1 /home/ros/.ros/flexcell/demo_runs.jsonl > "$E/77_run_record.jsonl"

echo "== 5. live canonical envelope probe (real /observe snapshot) =="
cat > "$E/_env_probe.py" <<'PYEOF'
import json
import time

import rclpy
from rclpy.action import ActionClient

from flexcell_interfaces.action import Observe
from flexcell_interfaces.msg import TaskContext
from flexcell_skills.canonical_state import (
    deserialize_envelope, serialize_envelope, validate_envelope)

rclpy.init()
node = rclpy.node.Node('m2_1_env_probe')
cli = ActionClient(node, Observe, '/observe')
assert cli.wait_for_server(timeout_sec=15.0), 'observe action unavailable'
goal = Observe.Goal()
goal.refresh = True
fut = cli.send_goal_async(goal)
while not fut.done():
    time.sleep(0.05)
gh = fut.result()
rf = gh.get_result_async()
while not rf.done():
    time.sleep(0.05)
ws = rf.result().result.world_state

text = serialize_envelope(ws, TaskContext())  # executor owns task at decide() time
env = deserialize_envelope(text)              # version gate must accept our own bytes
violations = validate_envelope(env)
print('WorldStateSchemaVersion:', env['WorldStateSchemaVersion'])
print('revision:', env['world_state']['revision'])
print('schema_version:', env['world_state']['schema_version'])
print('objects:', [(o['name'], o['klass'], o['available'], round(o['pose_age_s'], 3))
                   for o in env['world_state']['objects']])
print('zones:', [(z['id'], z['occupancy'], z['occupied_by']) for z in env['world_state']['zones']])
print('robot gripper:', env['world_state']['robot']['gripper_joint_name'],
      round(env['world_state']['robot']['gripper_position'], 4))
print('serialized bytes:', len(text))
print('violations:', violations if violations else 'NONE')
with open('/mnt/f/flexcell-stage/setup/acceptance/week15/m2_1_worldstate_v2/77_sample_envelope.json', 'w') as fh:
    fh.write(text)
rclpy.shutdown()
PYEOF
{ echo "=== live envelope probe | $(date -Is) ==="; source /opt/ros/jazzy/setup.bash; source install/setup.bash; python3 "$E/_env_probe.py" 2>&1; echo "RC=$?"; } > "$E/77_envelope.out" 2>&1
cat "$E/77_envelope.out" | tail -10

echo "== 6. parity vs att3 delivery baseline =="
cat > "$E/_parity.py" <<'PYEOF'
import json

BASE = '/mnt/f/flexcell-stage/setup/acceptance/week15/delivery_20260926/66_run_record_happy.jsonl'
NEW = '/mnt/f/flexcell-stage/setup/acceptance/week15/m2_1_worldstate_v2/77_run_record.jsonl'
base = json.loads(open(BASE).read().strip())
new = json.loads(open(NEW).read().strip())
keys_ok = sorted(base.keys()) == sorted(new.keys())
trace_ok = base['fsm_trace'] == new['fsm_trace']
outcome_ok = base['outcome'] == new['outcome']
steps_ok = len(base['steps']) == len(new['steps'])
print('baseline :', base['run_id'], 'outcome', base['outcome'], 'steps', len(base['steps']))
print('new      :', new['run_id'], 'outcome', new['outcome'], 'steps', len(new['steps']))
print('record keys identical :', keys_ok)
print('fsm_trace identical   :', trace_ok)
print('  baseline trace:', base['fsm_trace'])
print('  new      trace:', new['fsm_trace'])
print('outcome identical     :', outcome_ok)
print('step count identical  :', steps_ok)
verdict = 'PASS' if all([keys_ok, trace_ok, outcome_ok, steps_ok]) else 'FAIL'
print('PARITY:', verdict)
print('new zone errors: a=%.4f b=%.4f (tolerance 0.060)' % (new['zone_a_error_m'], new['zone_b_error_m']))
PYEOF
python3 "$E/_parity.py" 2>&1 | tee "$E/77_parity_check.out"

echo "== 7. clean stop =="
{ echo "=== flexcell stop | $(date -Is) ==="; bash "$CLI" stop; echo "RC=$?"; } > "$E/77_stop.out" 2>&1
grep -E "STOP OK|STOP INCOMPLETE" "$E/77_stop.out"
echo "== evidence files =="
ls "$E"
