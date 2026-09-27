#!/usr/bin/env bash
# 83d_battery_mid.sh — Step 0 (#20) battery part 2: recovery / exhaust /
# invalid / reset cases (61-battery semantics, week2 evidence dir).
source /opt/ros/jazzy/setup.bash
source /home/ros/agentic_workcell_ws/install/setup.bash
cd /home/ros/agentic_workcell_ws

E=/mnt/f/flexcell-stage/setup/acceptance/week2/m2_2_step0_ghost_fix
CLI=/tmp/flexcell_cli
C=src/flexcell/flexcell_skills/test/w1_client.py
mkdir -p "$E"

demo() { # <outfile>
  timeout 170 python3 "$C" --action demo --scenario "$SCEN" > "$E/$1" 2>&1
  tail -n 1 /home/ros/.ros/flexcell/demo_runs.jsonl > "$E/${1%.out}.jsonl"
  python3 - "$E/${1%.out}.jsonl" <<'PYEOF'
import json, sys
r = json.loads(open(sys.argv[1]).read().strip())
print('OUTCOME=%s err=%s trace=%s' % (r['outcome'], r['error_code'], ','.join(r['fsm_trace'])))
PYEOF
}

echo "== case B: recovery (inject once -> REOBSERVE -> retry -> success) =="
SCEN=recovery_demo_v1
python3 "$C" --action inject --inject "recovery_demo_v1:once" > /dev/null 2>&1
sleep 1
demo 83d_recovery_a.out
O=$(python3 -c "import json;print(json.loads(open('$E/83d_recovery_a.jsonl').read().strip())['outcome'])")
if [ "$O" != "0" ]; then
  echo "-- recovery attempt failed ($O); settle 30s, retry once --"
  sleep 30
  python3 "$C" --action inject --inject "recovery_demo_v1:once" > /dev/null 2>&1
  sleep 1
  demo 83d_recovery_b.out
  O=$(python3 -c "import json;print(json.loads(open('$E/83d_recovery_b.jsonl').read().strip())['outcome'])")
fi
echo "RECOVERY_OUTCOME=$O"

echo "== case C: exhaust (inject always -> BUDGET_EXHAUSTED, typed) =="
bash "$CLI" reset > "$E/83d_reset_before_exhaust.out" 2>&1
grep -o '"ok": [a-z]*' "$E/83d_reset_before_exhaust.out" | tail -1
SCEN=exhaust_demo_v1
python3 "$C" --action inject --inject "exhaust_demo_v1:always" > /dev/null 2>&1
sleep 1
demo 83d_exhaust.out
python3 "$C" --action inject --inject "" > /dev/null 2>&1

echo "== case D: invalid target (unreachable pose -> typed failure) =="
{
  echo "=== 83d_invalid | $(date -Is) | EXPECT: typed IK failure ==="
  timeout 120 python3 "$C" --action task --object target_box_a --pose 0.42 0 0.0175
  echo "RC=$?"
} > "$E/83d_invalid.out" 2>&1
grep -E '"outcome"|error_code|IK|detail' "$E/83d_invalid.out" | head -4

echo "== case E: reset after success (known-gap watch: attached objects) =="
bash "$CLI" reset > "$E/83d_reset_after_success.out" 2>&1
grep -oE '"ok": [a-z]*|"scene_cleared": [a-z]*' "$E/83d_reset_after_success.out" | tail -2

echo "== 83d DONE =="
