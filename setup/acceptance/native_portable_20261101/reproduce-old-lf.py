#!/usr/bin/env python3
"""Reproduce the original LF failure without loading a simulator or ROS client."""
import hashlib
import importlib.util
import json
from pathlib import Path

capsule=Path(__file__).resolve().parent
repo=capsule.parents[2]
receipt=json.loads((capsule/'receipt.json').read_text())
old=capsule/'verifier-before-portable-fix.py'
assert hashlib.sha256(old.read_bytes()).hexdigest()==receipt['files'][old.name]
binding=json.loads((repo/'setup/acceptance/native_audit_20261031/source-binding.json').read_text())
for name in ('scripts/native_cycle_gate.py','scripts/contact_gate.py','scripts/integrated_contact_gate.py',
             'src/flexcell/flexcell_skills/flexcell_skills/joint_follow.py'):
    data=(repo/name).read_bytes()
    assert b'\r\n' not in data, 'use a Git LF checkout for this counterexample'
    assert hashlib.sha256(data).hexdigest()==binding['source_files'][name]
spec=importlib.util.spec_from_file_location('native_verifier_b042',old)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
try:
    module.verify(repo/'setup/acceptance/native_audit_20261031',repo)
except AssertionError as exc:
    assert 'gate changed' in str(exc) and 'scripts/contact_gate.py' in str(exc)
    print(json.dumps(dict(status='OLD_LF_FAILURE_REPRODUCED',error=str(exc),robot_actions=0)))
else:
    raise RuntimeError('the original failure was not reproduced')
