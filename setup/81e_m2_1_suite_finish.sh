#!/usr/bin/env bash
# 81e_m2_1_suite_finish.sh — happy (re-seat) -> reset case (clean state) -> repeat
# -> regress (if /tmp/d2.sh) -> stop -> collect evidence
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
cd /home/ros/agentic_workcell_ws

E=/mnt/f/flexcell-stage/setup/acceptance/week15/m2_1_decision_policy
W=/mnt/f/flexcell-stage/setup/acceptance/week15
echo "loadavg: $(cat /proc/loadavg)"

echo "== happy (re-seat after the attached-box abort scenario) =="
bash /mnt/f/flexcell-stage/setup/61_w15_acceptance.sh happy > "$E/61_A_happy2.out" 2>&1
grep -E '"outcome"' "$E/61_A_happy2.out" | head -2

echo "== battery: reset (clean world-object state) =="
bash /mnt/f/flexcell-stage/setup/61_w15_acceptance.sh reset > "$E/61_E_reset.out" 2>&1
grep -o '"ok": [a-z]*' "$E/61_E_reset.out" | tail -1

echo "== battery: repeat (5 runs) =="
bash /mnt/f/flexcell-stage/setup/61_w15_acceptance.sh repeat > "$E/61_F_repeat.out" 2>&1
cat "$W/61_F_repeat_summary.out"

echo "== regress (day-2 suite, if present) =="
if [ -f /tmp/d2.sh ]; then
  bash /mnt/f/flexcell-stage/setup/61_w15_acceptance.sh regress > "$E/61_regress.out" 2>&1
  grep -cE "PASS|RC=0" "$E/61_regress.out" | xargs echo "regress pass markers:"
  tail -3 "$E/61_regress.out"
else
  echo "SKIP: /tmp/d2.sh absent (day-2 driver; orthogonal to the policy seam)"
fi

echo "== stop =="
{ echo "=== flexcell stop | $(date -Is) ==="; bash "$CLI" 2>/dev/null; bash "$CLI" stop 2>/dev/null || bash /tmp/flexcell_cli stop; echo "RC=$?"; } > "$E/81e_stop.out" 2>&1
grep -E "STOP OK|STOP INCOMPLETE" "$E/81e_stop.out"

echo "== evidence: decisions + parity =="
cp /home/ros/.ros/flexcell/decisions.jsonl "$E/decisions.jsonl"
wc -l "$E/decisions.jsonl" | xargs echo "decision records:"
python3 - <<'PYEOF'
import json
base = json.loads(open('/mnt/f/flexcell-stage/setup/acceptance/week15/delivery_20260926/66_run_record_happy.jsonl').read().strip())
new = json.loads(open('/mnt/f/flexcell-stage/setup/acceptance/week15/m2_1_decision_policy/61_A_happy2.out').read().split('RESULT ')[1].split('}RC=')[0] + '}')
print('baseline :', base['run_id'], base['outcome'], 'steps', len(base['steps']))
print('new      :', new['run_id'], new['outcome'], 'steps', len(new['steps']))
print('fsm_trace identical to att3 baseline:', base['fsm_trace'] == new['fsm_trace'])
print('  new trace:', new['fsm_trace'])
print('zone errors new: a=%.4f b=%.4f' % (new['zone_a_error_m'], new['zone_b_error_m']))
PYEOF
