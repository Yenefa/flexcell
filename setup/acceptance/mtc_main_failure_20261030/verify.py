#!/usr/bin/env python3
"""Preserve a recovered task as a rejected first-attempt qualification."""
import hashlib
import json
from pathlib import Path
import zipfile


def verify():
    archive = Path(__file__).with_name('main_40919257769.zip')
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == '15e2040644c981e51412fd9de45acea755882ea0fbb48cdc04de5116ecf9a7ed'
    with zipfile.ZipFile(archive) as z:
        def read(suffix):
            names = [n for n in z.namelist() if n.endswith(suffix)]
            assert len(names) == 1, suffix
            return z.read(names[0]).decode()
        window = json.loads(read('/window.json'))
        assert window['status'] == 'STOPPED' and window['no_replacements'] is True
        assert window['error'] == 'joint follow evidence: pick result missing or failed'
        assert len(window['episodes']) == 1
        result = window['episodes'][0]['result']
        assert result['status'] == 'PASS' and result['physical_tasks_dispatched'] == 1
        assert result['task']['outcome_val'] == 0 and result['task']['fsm_trace'][:3] == [
            'PICK_A(attempt=1):FAIL:ERR_MOTION_FAILED',
            'RECOVERY:REOBSERVE+RETRY(after PICK_A(attempt=1))', 'PICK_A(attempt=2):OK']
        picks = [json.loads(l) for l in read('/skills/pick.jsonl').splitlines()]
        assert len(picks) == 2
        first, second = picks
        assert first['outcome'] == '1' and first['error_code'] == 30
        assert first['planning_detail'] == 'no complete MTC solution' and first['mtc_stages'] == []
        assert first['detail'].startswith('MTC planning failed before execution:')
        assert second['outcome'] == '0' and second['error_code'] == 0
        stack = read('/stack.log')
        assert 'GOAL_STATE_INVALID' in stack
        identity = json.loads(read('/identity.stdout'))
        assert identity['source_revision'] == '69ba3d7924cb84784a177ab0efb66eb2d03f6662'
        assert identity['mismatches'] == []
        health = json.loads(read('/health_after.stdout'))
        assert health['ok'] is True and health['hard_fail'] == [] and len(health['checks']) == 19
        assert health['checks']['task_state'] == 'IDLE' and health['checks']['carry_engaged'] is False
    return dict(status='RECOVERED_TASK_REMAINS_REJECTED', source_revision=identity['source_revision'],
                workflow_run=40919257769, physical_tasks=1, pick_attempts=2,
                first_planning_execution_started=False, historical_failed_stage='UNKNOWN',
                default_admission='NO_GO')


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
