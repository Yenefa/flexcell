import json

BASE = '/mnt/f/flexcell-stage/setup/acceptance/week15/delivery_20260926/66_run_record_happy.jsonl'
NEW = '/mnt/f/flexcell-stage/setup/acceptance/week15/m2_1_worldstate_v2/77c_run_record.jsonl'
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
