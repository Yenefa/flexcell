#!/usr/bin/env bash
# 77b_m2_1_resume.sh — resume M2.1 acceptance after 77's two script bugs
# (missing install/setup.bash source; probe without rclpy spin). Stack is UP.
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
cd /home/ros/agentic_workcell_ws

E=/mnt/f/flexcell-stage/setup/acceptance/week15/m2_1_worldstate_v2
D=/mnt/f/flexcell-stage/setup/acceptance/week15/delivery_20260926
CLI=/tmp/flexcell_cli

echo "== health gate =="
{ echo "=== flexcell health (strict) | $(date -Is) ==="; bash "$CLI" health; echo "RC=$?"; } > "$E/77b_health.out" 2>&1
grep -c '"OK"' "$E/77b_health.out" | xargs echo "OK checks:"

echo "== canonical reset =="
{ echo "=== flexcell reset | $(date -Is) ==="; bash "$CLI" reset; echo "RC=$?"; } > "$E/77b_reset.out" 2>&1
grep -o '"ok": [a-z]*' "$E/77b_reset.out" | tail -1

echo "== happy demo (week1_demo_v1) =="
{
  echo "=== happy demo | $(date -Is) ==="
  timeout 170 python3 src/flexcell/flexcell_skills/test/w1_client.py --action demo --scenario week1_demo_v1
  echo "RC=$?"
} > "$E/77b_demo.out" 2>&1
grep -E '"outcome"|zone_a_error_m|zone_b_error_m|run_id' "$E/77b_demo.out" | head -6
tail -n 1 /home/ros/.ros/flexcell/demo_runs.jsonl > "$E/77b_run_record.jsonl"

echo "== live canonical envelope probe =="
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
    rclpy.spin_once(node, timeout_sec=0.05)   # w1_client pattern: spin to drive futures
gh = fut.result()
rf = gh.get_result_async()
while not rf.done():
    rclpy.spin_once(node, timeout_sec=0.05)
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
with open('/mnt/f/flexcell-stage/setup/acceptance/week15/m2_1_worldstate_v2/77b_sample_envelope.json', 'w') as fh:
    fh.write(text)
rclpy.shutdown()
PYEOF
{ echo "=== live envelope probe | $(date -Is) ==="; python3 "$E/_env_probe.py" 2>&1; echo "RC=$?"; } > "$E/77b_envelope.out" 2>&1
tail -10 "$E/77b_envelope.out"

echo "== parity vs att3 delivery baseline =="
cat > "$E/_parity.py" <<'PYEOF'
import json

BASE = '/mnt/f/flexcell-stage/setup/acceptance/week15/delivery_20260926/66_run_record_happy.jsonl'
NEW = '/mnt/f/flexcell-stage/setup/acceptance/week15/m2_1_worldstate_v2/77b_run_record.jsonl'
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
python3 "$E/_parity.py" 2>&1 | tee "$E/77b_parity_check.out"

echo "== clean stop =="
{ echo "=== flexcell stop | $(date -Is) ==="; bash "$CLI" stop; echo "RC=$?"; } > "$E/77b_stop.out" 2>&1
grep -E "STOP OK|STOP INCOMPLETE" "$E/77b_stop.out"
echo "== evidence files =="
ls "$E"
