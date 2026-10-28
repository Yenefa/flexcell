#!/usr/bin/env python3
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from verify_phase3_window_v2 import verify, HERE

assert verify()['status'] == 'FACTS_AND_SUPPORT_VERIFIED'
cases = ['empty_history', 'negative_only', 'hidden_upper_tail', 'wrong_history_code',
         'injected_history', 'duplicate_identity', 'missing_final', 'wrong_rise', 'dirty_health']
for case in cases:
    with tempfile.TemporaryDirectory(prefix='flexcell-phase3-v2-') as temporary:
        root = Path(temporary)
        archive, history = root / 'phase3', root / 'history'
        shutil.copytree(HERE, archive); shutil.copytree(HERE.parent / 'grasp_b001_20261025', history)
        path = history / 'stage_pick.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        if case in cases[:5]:
            if case == 'empty_history': rows = []
            for row in rows:
                if str(row.get('error_code')) == '23' and 'box_rise_m' in row:
                    if case == 'negative_only': row['box_rise_m'] = -abs(row['box_rise_m']) - .000001
                    elif case == 'hidden_upper_tail' and row['box_rise_m'] >= .02341603295382962:
                        row['box_rise_m'] = .005
                    elif case == 'wrong_history_code': row['error_code'] = 22
                    elif case == 'injected_history': row['injected'] = True
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        elif case == 'dirty_health':
            path = archive / 'health_after.json'; data = json.loads(path.read_text()); data['ok'] = False
            path.write_text(json.dumps(data))
        else:
            name = {'duplicate_identity':'logs/pick_window.jsonl','missing_final':'logs/carry_window.jsonl','wrong_rise':'B5.jsonl'}[case]
            path = archive / name; rows = [json.loads(line) for line in path.read_text().splitlines()]
            if case == 'duplicate_identity': rows[1]['evidence_id'] = rows[0]['evidence_id']
            elif case == 'missing_final': rows = [row for row in rows if not row.get('final')]
            else: rows[1]['rise_m'] = .04
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        try: verify(archive, history)
        except (AssertionError, ValueError, KeyError): pass
        else: raise AssertionError('accepted mutation: '+case)
        if case == 'hidden_upper_tail':
            # This preserves v1's n/negative/median claims while hiding the
            # overlapping upper tail: v1 accepts it, v2 rejects it.
            proc = subprocess.run([sys.executable, str(HERE/'verify_phase3_window.py'), str(archive), str(history)],
                                   capture_output=True)
            assert proc.returncode == 0, proc.stdout.decode()[-1000:]
print('10/10: original accepted, nine corruptions rejected; hidden upper tail defeats unchanged v1')
