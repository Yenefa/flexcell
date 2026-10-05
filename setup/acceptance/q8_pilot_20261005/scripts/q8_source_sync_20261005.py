from pathlib import Path
import subprocess
import hashlib
import json

source = Path('/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/code-clone')
dest = Path('/home/ros/agentic_workcell_ws')
receipt = dest / 'setup/acceptance/q8_pilot_20261005/source_sync_manifest.json'
previous = json.loads(receipt.read_text()) if receipt.exists() else {}
names = [
    'setup/32_day2_acceptance.sh',
    'setup/94_scenario_runner.py',
    'src/flexcell/flexcell_skills/flexcell_skills/jev_backends.py',
    'src/flexcell/flexcell_skills/flexcell_skills/jev_policy.py',
    'src/flexcell/flexcell_skills/flexcell_skills/hybrid_policy.py',
    'src/flexcell/flexcell_skills/flexcell_skills/contracts/routing_audit.py',
    'src/flexcell/flexcell_skills/test/test_clef_backend.py',
    'src/flexcell/flexcell_skills/test/test_routing_audit.py',
    'src/flexcell/flexcell_skills/test/test_acceptance_gate.py',
]
for name in names:
    path = dest / name
    if path.exists():
        baseline = subprocess.run(['git', '-C', str(dest), 'show', '7dfe004:' + name], capture_output=True)
        actual = path.read_bytes()
        prior_runner = (source / name).read_bytes()
        if name == 'setup/94_scenario_runner.py':
            prior_runner = prior_runner.replace(b"    if not args.dry_run and args.policy == 'hybrid' and deployment is None:\n        ap.error('hybrid execution requires --deployment for routing provenance')\n", b'').replace(b"        if deployment and deployment.get('runtime_fingerprint') != baseline_profile:\n            ap.error('deployment differs from the qualifying smoke runtime')\n", b'').replace(b"                     (not deployment or (r.get('routing_audit') or {}).get('ok') is True) and\n", b'')
        if (actual not in (baseline.stdout, (source / name).read_bytes(), prior_runner)
                and hashlib.sha256(actual).hexdigest() != previous.get(name)):
            raise SystemExit('Refusing unknown local changes: ' + name)
for name in names:
    path = dest / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((source / name).read_bytes())
    print('SYNC', name)
receipt.parent.mkdir(parents=True, exist_ok=True)
receipt.write_text(json.dumps({name: hashlib.sha256((dest / name).read_bytes()).hexdigest()
                               for name in names}, indent=2) + '\n')
