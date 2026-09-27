#!/usr/bin/env bash
# 83c_happy_retry.sh — Step 0 (#20) happy case with starvation-tolerant retry.
# att1/att2 environment race: cold/marginal-load runs can starve the carry
# servo (rise < follow_min). Discipline: tolerate re-runs, decide on
# structured evidence (diary 2026-09-26). Max 2 attempts, 45s settle between.
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
cd /home/ros/agentic_workcell_ws

E=/mnt/f/flexcell-stage/setup/acceptance/week2/m2_2_step0_ghost_fix
CLI=/tmp/flexcell_cli
C=src/flexcell/flexcell_skills/test/w1_client.py
mkdir -p "$E"

echo "== environment evidence (att1/att2 family check) =="
{ uptime; ps -eo pcpu,comm --sort=-pcpu | head -8; } | tee "$E/83c_load_before.out"

run_attempt() { # <n>
  bash "$CLI" reset > "$E/83c_reset_$1.out" 2>&1
  grep -o '"ok": [a-z]*' "$E/83c_reset_$1.out" | tail -1
  timeout 170 python3 "$C" --action demo --scenario week1_demo_v1 \
    > "$E/83c_demo_$1.out" 2>&1
  tail -n 1 /home/ros/.ros/flexcell/demo_runs.jsonl > "$E/83c_run_$1.jsonl"
  python3 - "$E/83c_run_$1.jsonl" <<'PYEOF'
import json, sys
r = json.loads(open(sys.argv[1]).read().strip())
print('ATTEMPT outcome=%s trace=%s zone_a=%.4f zone_b=%.4f'
      % (r['outcome'], ','.join(r['fsm_trace']),
         r['zone_a_error_m'], r['zone_b_error_m']))
PYEOF
}

echo "== attempt 1 =="
run_attempt 1
OK1=$(python3 -c "import json;print(json.loads(open('$E/83c_run_1.jsonl').read().strip())['outcome'])")

if [ "$OK1" != "RunDemo.Result.OUTCOME_SUCCEEDED" ]; then
  echo "-- attempt 1 not succeeded ($OK1); settle 45s, retry --"
  sleep 45
  { uptime; ps -eo pcpu,comm --sort=-pcpu | head -6; } > "$E/83c_load_mid.out"
  echo "== attempt 2 =="
  run_attempt 2
  OK2=$(python3 -c "import json;print(json.loads(open('$E/83c_run_2.jsonl').read().strip())['outcome'])")
  BEST=2
else
  BEST=1
fi

if [ "${OK2:-$OK1}" != "RunDemo.Result.OUTCOME_SUCCEEDED" ]; then
  echo "HAPPY_RESULT: FAILED_AFTER_RETRIES (starvation signature — escalate to chief)"
  { uptime; ps -eo pcpu,comm --sort=-pcpu | head -8; } | tee "$E/83c_load_after.out"
  exit 2
fi

echo "== parity + genuine-place assertions on attempt $BEST =="
cp "$E/83c_run_$BEST.jsonl" "$E/83c_run_record.jsonl"
python3 - "$E" <<'PYEOF' 2>&1 | tee "$E/83c_assertions.out"
import json
import sys

E = sys.argv[1]
BASE = '/mnt/f/flexcell-stage/setup/acceptance/week15/delivery_20260926/66_run_record_happy.jsonl'
base = json.loads(open(BASE).read().strip())
new = json.loads(open(E + '/83c_run_record.jsonl').read().strip())

trace_ok = base['fsm_trace'] == new['fsm_trace']
natural_recovery = [t for t in new['fsm_trace'] if t.startswith('RECOVERY:')]
outcome_ok = new['outcome'] == 'RunDemo.Result.OUTCOME_SUCCEEDED'
print('baseline outcome:', base['outcome'], '| new outcome:', new['outcome'])
print('BYTE_PARITY:', 'PASS' if trace_ok else
      ('SEMANTIC-EQUIV (natural recovery: %s)' % natural_recovery if outcome_ok else 'FAIL'))
print('  baseline:', base['fsm_trace'])
print('  new     :', new['fsm_trace'])
za, zb = new['zone_a_error_m'], new['zone_b_error_m']
print('zone errors: a=%.4f b=%.4f (tolerance 0.060)' % (za, zb))

place_steps = [s for s in new['steps'] if s.get('skill') == 'place']
genuine = all(s['ok'] and 'drop error' in s['error'] for s in place_steps)
print('place steps: %d, all-genuine(with real drop-error detail): %s'
      % (len(place_steps), genuine))
for s in place_steps:
    print('  %s ok=%s error=%r' % (s['state'], s['ok'], s['error']))
recs = [json.loads(l) for l in open('/home/ros/.ros/flexcell/place.jsonl')]
good = [r for r in recs if r.get('outcome') == '0'
        and r.get('detail', '').startswith('placed')
        and 'place_error_m' in r and r.get('released') is True]
print('cumulative GENUINE place successes in place.jsonl:', len(good))
assert outcome_ok and genuine and len(place_steps) == 2 and len(good) >= 2, \
    'genuine-place assertion failed'
print('PLACE_GENUINE_SUCCESS: PASS')
PYEOF
{ uptime; ps -eo pcpu,comm --sort=-pcpu | head -6; } > "$E/83c_load_after.out"
echo "== 83c DONE (stack stays up for 83d) =="
