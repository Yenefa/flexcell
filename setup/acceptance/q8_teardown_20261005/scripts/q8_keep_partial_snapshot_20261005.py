"""Retain the mistakenly early frozen reset snapshot under an explicit name."""
import hashlib
import json
from pathlib import Path

root = Path('/home/ros/agentic_workcell_ws/setup/acceptance/q8_teardown_20261005')
dest = Path('/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/code-clone/setup/acceptance/q8_teardown_20261005')
receipt_path = dest / 'SHA256SUMS.json'
receipt = json.loads(receipt_path.read_text())
partial = next(r for r in receipt if r['original'] == str(root / 'reset_rpc_after/reset20.json'))
data = (dest / partial['copy']).read_bytes()
count = len(json.loads(data))
for r in receipt:
    if r['original'] not in (str(root / 'reset_rpc_after/reset20.json'), str(root / 'reset_rpc_after/reset20.log')):
        continue
    source = dest / r['copy']
    data = source.read_bytes()
    assert hashlib.sha256(data).hexdigest() == r['sha256']
    original = Path(r['original'])
    snapshot_name = 'reset20_partial_%d%s' % (count, original.suffix)
    snapshot = root / 'reset_rpc_after/snapshots' / snapshot_name
    snapshot.parent.mkdir(exist_ok=True)
    assert not snapshot.exists()
    snapshot.write_bytes(data)
    new_copy = 'reset_rpc_after/snapshots/' + snapshot_name + ('.raw' if original.suffix == '.json' else '')
    target = dest / new_copy
    assert dest.resolve() in source.resolve().parents and dest.resolve() in target.resolve().parents
    target.parent.mkdir(exist_ok=True)
    assert not target.exists()
    source.rename(target)
    r.update(original=str(snapshot), copy=new_copy)
receipt_path.write_text(json.dumps(receipt, indent=2)+'\n')
print('Preserved early snapshot, rows=', count)
