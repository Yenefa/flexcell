
import json, sys, copy
from pathlib import Path
WT = Path('/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp')
sys.path.insert(0, str(WT/'evolution'/'experience'))
import store, verify_provenance as vp, seed_from_evidence as sfe

seed = json.loads((WT/'setup/acceptance/evobot_lead_p3_record_20261112/seed_margin_consumed.json').read_text())[0]
ok, why, rec = sfe.review_seed(seed, None)
print('ACCEPTED:', ok, '|', why)
print('evidence_files:')
for f in rec.get('evidence_files') or []: print('   ', f)
print('record_sha256:', rec.get('record_sha256'))
print('provenance_verified:', rec.get('provenance_verified'), '| validated:', rec.get('validated'), '(validated must stay False)')
print('failure_class:', rec.get('failure_class'), '| store_version:', rec.get('store_version'))
print()
print('=== tamper tests on the FINAL three facts (each must REJECT) ===')
def tamper(label, mut):
    s = copy.deepcopy(seed); mut(s)
    ok, why, _ = sfe.review_seed(s, None)
    print('%-38s -> %s  %s' % (label, 'ACCEPT!!' if ok else 'REJECT', why[:110]))
tamper('clearance_m 0.05 -> 0.06', lambda s: s['evidence'].__setitem__('clearance_m', 0.06))
tamper('place_error_m 9.658 -> 10.658 mm', lambda s: s['evidence'].__setitem__('place_error_m', 0.010658022849775898))
tamper('final_position_error_m -> 0.0', lambda s: s['evidence'].__setitem__('final_position_error_m', 0.0))
tamper('invented margin_m 0.0014', lambda s: s['evidence'].__setitem__('margin_m', 0.0014))
tamper('banned position_tolerance_m', lambda s: s['evidence'].__setitem__('position_tolerance_m', 0.02))
tamper('lesson -> planning strategy', lambda s: s.__setitem__('lesson','Choose a free destination for each object before sending the second one, and order the moves so a later stage is not blocked by an earlier one.'))
tamper('lesson -> landing-spot wording', lambda s: s.__setitem__('lesson','Give each object a distinct landing spot inside the bin using its coordinate offset so the spots do not collide.'))
print()
print('=== arithmetic re-derivation from the cited run ===')
plan = json.loads((WT/seed['source_run']/'plan.json').read_text())
a = plan['stages'][0]['place_pose']; b = plan['stages'][1]['place_pose']
meas = json.loads((WT/seed['source_run']/'sim/skills/place.jsonl').read_text().strip())['box_after']
import math
sep_cmd = math.dist(a[:2], b[:2]); err = math.dist(meas[:2], a[:2]); sep_meas = math.dist(meas[:2], b[:2])
print('commanded separation      : %.6f m = %.3f mm' % (sep_cmd, sep_cmd*1000))
print('accepted error limit      : %.4f m = %.1f mm   (plan.position_tolerance_m)' % (plan['position_tolerance_m'], plan['position_tolerance_m']*1000))
print('measured error            : %.6f m = %.3f mm   (inside limit: %s)' % (err, err*1000, err < plan['position_tolerance_m']))
print('nominal margin over clear : %.3f mm' % ((sep_cmd - plan['clearance_m'])*1000))
print('margin left after error   : %.3f mm  (negative = shortfall)' % ((sep_meas - plan['clearance_m'])*1000))
print('clearance                 : %.4f m = %.1f mm' % (plan['clearance_m'], plan['clearance_m']*1000))
