import hashlib
import importlib.util
import json
from pathlib import Path
import re


AUTHORITY = Path('/home/ros/agentic_workcell_ws')
ROOT = AUTHORITY / 'setup/acceptance/transferbench_t1_20261006'
TREES = (AUTHORITY, Path('/home/ros/.codex/worktrees/16d1/flexcell'), Path('/mnt/c/dev/flexcell'))
problems = []
former = []
for tree in TREES:
    for folder in ('school_clef_route_20261006', 'route_hardening_20261006',
                   'place_transport_20261006', 'transferbench_foundation_20261006'):
        parent = tree / 'setup/acceptance' / folder
        raw = json.loads((parent / 'SHA256SUMS.json').read_text())
        if isinstance(raw, list):
            entries = [(row.get('path', row.get('copy')), row['sha256']) for row in raw]
        else:
            entries = [(rel, row if isinstance(row, str) else row['sha256']) for rel, row in raw.items()]
        errors = [rel for rel, expected in entries
                  if hashlib.sha256((parent / rel).read_bytes()).hexdigest() != expected]
        problems.extend(str(parent / rel) for rel in errors)
        former.append(dict(tree=str(tree), receipt=folder, files=len(entries), unchanged=not errors))
spec = importlib.util.spec_from_file_location('cost', AUTHORITY / 'setup/125_transfer_cost.py')
cost = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cost)
ledger = cost.read_ledger(ROOT / 'cost.jsonl')
correction = json.loads((ROOT / 'adjudication_v2/correction_manifest.json').read_text())
for rel, pin in correction['original_inputs'].items():
    if cost.pin(pin['path']) != pin:
        problems.append('original input changed: ' + rel)
trials = [r['payload'] for r in ledger[1:] if r['payload']['kind'] == 'trial']
report = json.loads((ROOT / 'adjudication_v2/report.json').read_text())
actual_run_ids, controller_rows, final_goals = [], [], []
for arm in ('fsm', 'hybrid'):
    for attempt in sorted((ROOT / arm).glob('attempt*')):
        episode = json.loads((attempt / 'episode.json').read_text())
        actual_run_ids.append(episode['run_id'])
        rows = [json.loads(row) for row in (attempt / 'raw/controller_transport.jsonl').read_text().splitlines()]
        controller_rows.extend(rows)
        final_goals.extend(row for row in rows if row['event'] == 'controller_goal_terminal')
if len(set(actual_run_ids)) != 6 or set(actual_run_ids) != {t['trial_id'] for t in trials}:
    problems.append('trial/run ID mismatch or replacement')
if any(row['status'] != 4 for row in final_goals):
    problems.append('non-success controller terminal')
if any(row['event'] == 'controller_goal_quarantined' for row in controller_rows):
    problems.append('controller goal quarantined')
secret_candidates = []
for path in ROOT.rglob('*'):
    if path.is_file() and '__pycache__' not in path.parts:
        if re.search(rb'sk-[A-Za-z0-9_-]{24,}', path.read_bytes()):
            secret_candidates.append(str(path.relative_to(ROOT)))
        if path.suffix in ('.gguf', '.so', '.dll') or 'install' in path.relative_to(ROOT).parts or 'build' in path.relative_to(ROOT).parts:
            problems.append('forbidden artifact: ' + str(path))
problems.extend('possible credential: ' + name for name in secret_candidates)
value = dict(ok=not problems, problems=problems, former_receipts=former,
             original_ledger_verified_rows=len(ledger), original_inputs_unchanged=len(correction['original_inputs']),
             actual_run_ids=actual_run_ids, no_replacement=True,
             corrected_cells=report['trial_cells'],
             controller_goal_terminals=len(final_goals), all_controller_terminal_status_4=all(r['status'] == 4 for r in final_goals),
             controller_quarantines=sum(r['event'] == 'controller_goal_quarantined' for r in controller_rows),
             AC90='NOT_RUN', qualification='FROZEN', n_ge_50='FROZEN',
             physical_safety_acceptance='NOT_RUN',
             network_stability='NOT_ACCEPTED; startup timeout and one of five follow-up TCP probes timed out')
with (ROOT / 'validation/delivery_attempt01.json').open('x') as stream:
    json.dump(value, stream, indent=2)
    stream.write('\n')
print(json.dumps(dict(ok=value['ok'], original_inputs=len(correction['original_inputs']),
                      previous_receipts=len(former), controller_terminals=len(final_goals), problems=problems)))
raise SystemExit(1 if problems else 0)
