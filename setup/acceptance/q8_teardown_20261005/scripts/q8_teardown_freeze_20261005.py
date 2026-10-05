"""Freeze new evidence with exact-byte copies; do not copy crash-core bytes."""
import hashlib
import json
from pathlib import Path
import re

repo = Path('/home/ros/agentic_workcell_ws')
root = repo / 'setup/acceptance/q8_teardown_20261005'
win = Path('/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/code-clone')
dest = win / 'setup/acceptance/q8_teardown_20261005'
dest.mkdir(parents=True, exist_ok=True)
receipt_path = dest / 'SHA256SUMS.json'
receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else []
originals = {r['original']: r for r in receipt}
for log in root.glob('*.log'):
    if re.match(r'(smoke|baseline)_[0-9.]+_\d+_', log.name):
        assert 'batch summary:' in log.read_text(), 'Do not freeze an active batch: ' + log.name
rpc_resets = root / 'reset_rpc_after/reset20.json'
if rpc_resets.exists():
    rpc_rows = json.loads(rpc_resets.read_text())
    assert len(rpc_rows) == 20, 'Do not freeze an active reset collection'

def freeze(source, relative):
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if source.suffix in ('.json', '.jsonl'):
        relative += '.raw'
    target = dest / relative
    if str(source) in originals:
        previous = originals[str(source)]
        assert previous['sha256'] == digest, 'Frozen evidence changed: ' + str(source)
        assert target.read_bytes() == data
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    originals[str(source)] = dict(original=str(source), copy=relative,
                                 sha256=digest, bytes=len(data))

for source in sorted(root.iterdir()):
    if not source.is_file() or source.name.startswith('core.python3.') and not source.name.endswith('.txt'):
        continue
    if source.name in ('summary.json', 'SHA256SUMS.json', 'core_metadata.json', 'collection_note.json'):
        continue  # Freeze final statistics after both arms finish.
    freeze(source, 'diagnostics/' + source.name)

for source in sorted((root / 'reset_rpc_after').glob('*')):
    if source.is_file():
        freeze(source, 'reset_rpc_after/' + source.name)

for source in sorted((root / 'final_readiness').glob('*')):
    if source.is_file():
        freeze(source, 'final_readiness/' + source.name)

scripts = Path('/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/pm-work')
for name in (
    'q8_teardown_probe_20261005.py', 'q8_native_worker_probe_20261005.py',
    'q8_capture_core_20261005.sh', 'q8_native_diag_20261005.sh',
    'q8_reset_probe_20261005.py', 'q8_reset_rpc_probe_20261005.py',
    'q8_reset_rpc_run_20261005.sh', 'q8_rpc_process_control_20261005.py',
    'q8_rpc_process_control_20261005.sh', 'q8_rpc_validate_20261005.sh',
    'q8_rpc_reset_summary_20261005.py', 'q8_keep_partial_snapshot_20261005.py',
    'q8_rpc_align_transaction_20261005.py', 'q8_teardown_run_20261005.sh',
    'q8_probe_20261005.py', 'q8_report_20261005.py',
    'q8_teardown_finish_20261005.sh', 'q8_teardown_verify_final_20261005.py',
    'q8_teardown_align_final_20261005.py', 'q8_teardown_freeze_20261005.py',
):
    freeze(scripts / name, 'scripts/' + name)

for log in root.glob('*.log'):
    if not re.match(r'(smoke|baseline)_[0-9.]+_\d+_', log.name):
        continue
    paths = re.findall(r'batch summary: (.+)', log.read_text())
    if not paths:
        continue
    batch = Path(paths[-1])
    freeze(batch, 'batches/' + batch.name)
    for line in batch.read_text().splitlines():
        row = json.loads(line)
        if row.get('episode'):
            episode = Path(row['episode'])
            freeze(episode, 'episodes/' + episode.name)

cores = []
for core in root.glob('core.python3.*'):
    if core.name.endswith('.txt'):
        continue
    cores.append(dict(path=str(core), bytes=core.stat().st_size,
                      sha256=hashlib.sha256(core.read_bytes()).hexdigest(), archived=False))
(dest / 'core_metadata.json').write_text(json.dumps(cores, indent=2) + '\n')
(dest / 'collection_note.json').write_text(json.dumps(dict(
    reset_probe_children=20, reset_probe_each_rc=0, reset_probe_each_ok=True,
    outer_wrapper_rc=1, outer_wrapper_error='unexpected EOF after probe completion',
    cause='The running shell script was edited; child results were already saved.',
    subsequent_wrapper_syntax_check_rc=0), indent=2) + '\n')

resets = json.loads((root / 'reset20.json').read_text())
assert len(resets) == 20 and all(r['process_rc'] == 0 and r['payload']['ok'] is True for r in resets)
probes = json.loads((root / 'after100.json').read_text())
assert len(probes) == 100 and all(r['worker_rc'] == 0 and r['received_pose'] for r in probes)
receipt_path.write_text(json.dumps(list(originals.values()), indent=2) + '\n')
print(json.dumps(dict(archived=len(originals), subscriber_passed=len(probes),
                     reset_passed=len(resets), core_bytes_archived=False)))
