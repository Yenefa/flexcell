#!/usr/bin/env python3
"""Verify the archived bytes and independently recompute the diagnostic counts."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
receipt = json.loads((root / 'receipt.json').read_text())
for name, expected in receipt['files'].items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
rows = [json.loads(line) for line in (root / 'attempts.jsonl').read_text().splitlines()
        if line.startswith('{"kind":')]
assert len(rows) == 56
facts = {}
for label in ('zero_offset_control', 'known_reachable_offset', 'place_hover_offset'):
    attempts = [r for r in rows if r['kind'] == 'attempt' and r['case'] == label]
    assert len(attempts) == 16
    assert [r['index'] for r in attempts] == list(range(16))
    ik = [r for r in attempts if r['ik_success']]
    valid = [r for r in ik if r['constraint_satisfied']]
    facts[label] = {'attempts': 16, 'ik': len(ik), 'valid': len(valid)}
    assert all(r['point_error_m'] <= 1e-4 for r in valid)
assert facts['zero_offset_control'] == {'attempts': 16, 'ik': 16, 'valid': 16}
assert facts['known_reachable_offset'] == {'attempts': 16, 'ik': 10, 'valid': 0}
assert facts['place_hover_offset'] == {'attempts': 16, 'ik': 16, 'valid': 0}
assert next(r for r in rows if r['kind'] == 'reference' and r['case'] == 'known_reachable_offset')['constraint_satisfied']
assert receipt['physical_simulation_windows_started'] == 0
assert receipt['untracked_before_after_equal'] is True
assert receipt['colcon_checks'] == 661 and receipt['failures'] == 0
print(json.dumps({'status': 'OFFLINE_COUNTEREXAMPLE_REPRODUCED', 'cases': facts,
                  'exact_historical_planning_scene': 'UNKNOWN', 'default_admission': 'NO_GO'}, indent=2))
