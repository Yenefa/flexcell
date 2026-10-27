#!/usr/bin/env python3
"""Verify raw functional facts; the original window remains STOPPED."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def verify(root):
    def document(path):
        return json.loads((root / path).read_text())
    manifest = document('raw-copy-manifest.json')
    for name, record in manifest.items():
        data = (root / name).read_bytes()
        assert len(data) == record['size_bytes'], name
        assert hashlib.sha256(data).hexdigest() == record['sha256'], name
    original = document('original_window.json')
    assert original['status'] == 'STOPPED'
    assert 'result.json' in original['error']
    records, identities, goals = [], [], set()
    for index in range(1, 6):
        prefix = 'trial-%02d/' % index
        raw = (root / prefix / 'task.stdout').read_text()
        assert raw.count('RESULT ') == 1
        task = json.loads(raw.split('RESULT ', 1)[1])
        assert task['goal_uuid'] not in goals
        goals.add(task['goal_uuid'])
        health = document(prefix + 'health_after.stdout')
        assert health['ok'] is True and health['hard_fail'] == []
        assert health['checks']['task_state'] == 'IDLE'
        assert health['checks']['carry_engaged'] is False
        assert document(prefix + 'reset_after.stdout')['ok'] is True
        collection = document(prefix + 'collection.json')
        assert collection['rosbag_exit'] == 0 and collection['errors'] == []
        identity = document(prefix + 'identity.stdout')
        assert identity['mismatches'] == []
        identities.append(identity['source_tree_sha256'])
        picks = [json.loads(line) for line in (root / prefix / 'pick.jsonl').read_text().splitlines()]
        if index < 5:
            assert task['outcome_val'] == 0 and task['error_code'] == 'ERR_NONE'
            assert document(prefix + 'result.json')['status'] == 'PASS'
            if index == 3:
                assert task['object_a_at_zone'] is True and task['object_b_at_zone'] is True
            else:
                assert task['object_at_place'] is True
            if index == 4:
                assert len(picks) == 2 and sum(p.get('injected') is True for p in picks) == 1
        else:
            assert task['outcome_val'] == 1 and task['error_code'] == 'ERR_RECOVERY_EXHAUSTED'
            assert task['object_at_place'] is False
            assert math.isnan(task['final_position_error_m'])
            assert len(picks) == 2 and all(p.get('injected') is True and p['error_code'] == 23 for p in picks)
            assert not (root / prefix / 'result.json').exists()
            assert 'Out of range float values are not JSON compliant: nan' in (root / prefix / 'harness.log').read_text()
        records.append(dict(trial=index, goal_uuid=task['goal_uuid'], outcome=task['outcome'],
                            error_code=task['error_code'], cleanup_health='PASS'))
    assert len(set(identities)) == 1
    return dict(schema_version=1, status='RAW_FUNCTIONAL_FACTS_VERIFIED',
        original_window_status='STOPPED', original_failure='NaN report serialization after cleanup',
        reporting_qualification='NOT_GRANTED_BY_ORIGINAL_WINDOW',
        trials=records, new_robot_runs=0, source_tree_sha256=identities[0],
        scope='Five functional tasks; not a reliability estimate or grasp-cause inference')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=Path(__file__).parent / 'core-v1')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = verify(args.archive)
    if args.out:
        with args.out.open('x') as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write('\n')
    print(json.dumps(result, indent=2))
