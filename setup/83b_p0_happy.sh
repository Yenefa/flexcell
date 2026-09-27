#!/usr/bin/env bash
# 83b_p0_happy.sh — Step 0 (#20) runtime acceptance, ONE bounded foreground run:
# start -> health -> reset -> happy demo -> parity vs delivery baseline ->
# FIRST-GENUINE place.jsonl SUCCESS assertion. ~5 min budget.
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
cd /home/ros/agentic_workcell_ws

E=/mnt/f/flexcell-stage/setup/acceptance/week2/m2_2_step0_ghost_fix
CLI=/tmp/flexcell_cli
tr -d "\r" < /mnt/f/flexcell-stage/setup/flexcell > "$CLI"

echo "== 1. managed start =="
{ t0=$(date +%s); bash "$CLI" start; rc=$?; t1=$(date +%s);
  echo "START_DURATION_S=$((t1-t0))"; echo "RC=$rc"; } > "$E/83b_start.out" 2>&1
grep -E "START OK|START FAILED|START_DURATION_S" "$E/83b_start.out"

echo "== 2. health gate =="
{ bash "$CLI" health; echo "RC=$?"; } > "$E/83b_health.out" 2>&1
echo "OK checks: $(grep -c '"OK"' "$E/83b_health.out")"

echo "== 3. canonical reset =="
{ bash "$CLI" reset; echo "RC=$?"; } > "$E/83b_reset.out" 2>&1
grep -o '"ok": [a-z]*' "$E/83b_reset.out" | tail -1

echo "== 4. happy demo (week1_demo_v1) =="
{
  echo "=== happy demo | $(date -Is) ==="
  timeout 170 python3 src/flexcell/flexcell_skills/test/w1_client.py --action demo --scenario week1_demo_v1
  echo "RC=$?"
} > "$E/83b_demo.out" 2>&1
grep -E '"outcome"|zone_a_error_m|zone_b_error_m|run_id' "$E/83b_demo.out" | head -5
tail -n 1 /home/ros/.ros/flexcell/demo_runs.jsonl > "$E/83b_run_record.jsonl"

echo "== 5. parity vs att3 delivery baseline =="
python3 - "$E" <<'PYEOF' 2>&1 | tee "$E/83b_parity_check.out"
import json
import sys

E = sys.argv[1]
BASE = '/mnt/f/flexcell-stage/setup/acceptance/week15/delivery_20260926/66_run_record_happy.jsonl'
NEW = E + '/83b_run_record.jsonl'
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

echo "== 6. FIRST genuine place.jsonl SUCCESS assertion =="
python3 - "$E" <<'PYEOF' 2>&1 | tee "$E/83b_place_genuine.out"
import json
import sys

E = sys.argv[1]
recs = [json.loads(l) for l in open('/home/ros/.ros/flexcell/place.jsonl')]
good = [r for r in recs
        if r.get('outcome') == '0'
        and r.get('detail', '').startswith('placed')
        and 'place_error_m' in r
        and r.get('evidence_id')
        and r.get('released') is True]
print('place requests in full history:', len(recs))
print('GENUINE place successes:', len(good))
for r in good:
    print('  %s %s drop_err=%.4f released=%s evidence=%s elapsed=%dms'
          % (r['request_id'], r['object_name'], r['place_error_m'],
             r['released'], r['evidence_id'], r['elapsed_ms']))
# ghost check: any SUCCESS-shaped record from THIS run must be genuine
demo = json.loads(open(E + '/83b_run_record.jsonl').read().strip())
place_steps = [s for s in demo['steps'] if s.get('skill') == 'place']
print('demo place steps:', len(place_steps))
for s in place_steps:
    print('  %s ok=%s error=%r' % (s['state'], s['ok'], s['error']))
assert len(good) >= 2, 'expected >=2 genuine successes (one per leg)'
assert all(s['ok'] and 'drop error' in s['error'] for s in place_steps), \
    'demo place steps must now carry real drop-error detail'
print('PLACE_GENUINE_SUCCESS: PASS')
PYEOF

echo "== 83b DONE (stack stays up for 83c battery) =="
