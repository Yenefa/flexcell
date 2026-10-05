import json
from pathlib import Path

root = Path('/home/ros/agentic_workcell_ws/setup/acceptance/q8_teardown_20261005')
rows = json.loads((root / 'reset_rpc_after/reset20.json').read_text())
assert len(rows) == 20 and all(row['process_rc'] == 0 and row['payload']['ok'] is True for row in rows)
calls = []
for row in rows:
    report = row['payload']['report']
    for name in ('target_box_a', 'target_box_b'):
        assert report['respawn ' + name] is True
        attempts = report['respawn_details ' + name]['attempts']
        calls.append(attempts)
        for call in report['canonical_rpc ' + name]:
            assert call['ok'] is True
            calls.append(call['attempts'])
for attempts in calls:
    assert 1 <= len(attempts) <= 3
    assert all(a['worker_rc'] == 0 for a in attempts)
    assert attempts[-1]['transport_ok'] is True and attempts[-1]['response_data'] is True
    assert all(a['transport_ok'] is False for a in attempts[:-1])
summary = dict(resets=20, passed=20, pose_commands=len(calls),
               native_attempts=sum(len(a) for a in calls),
               recovered_pose_commands=sum(len(a)>1 for a in calls),
               failed_native_exits=0, service_rejections=0,
               outer_wrapper_rc=0)
(root / 'rpc_reset_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps(summary))
