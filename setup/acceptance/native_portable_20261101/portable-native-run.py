"""Replay the frozen LF tree in a child interpreter with no site packages."""
import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys

parser=argparse.ArgumentParser()
parser.add_argument('--repo',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
script=args.repo/'setup/acceptance/native_audit_20261031/verify.py'
with args.out.open('xb') as stdout, args.out.with_suffix('.stderr').open('xb') as stderr:
    process=subprocess.run([sys.executable,'-I','-S','-B',str(script)],cwd=args.repo,
        stdout=stdout,stderr=stderr)
assert process.returncode==0,args.out.with_suffix('.stderr').read_text()
data=json.loads(args.out.read_bytes())
assert data['status']=='NATIVE_AUDIT_LIFETIME_REPLAY_PASS'
assert data['patched']['source_revision_metadata']=='INVALID_TRAILING_CR'
assert data['historical']['status']=='STOPPED' and data['default_admission']=='NO_GO'
assert data['verification_sources']['policy']=='CRLF_PAIRS_TO_LF_ONLY'
assert len(data['verification_sources']['files'])==4
assert all(o['observed_line_endings']=='LF' for o in data['verification_sources']['files'].values())
receipt=dict(status=data['status'],platform=platform.platform(),python=sys.version,
    exit_code=process.returncode,isolated=True,site_packages=False,canonical_gate_files=4,
    patched_source_revision_metadata=data['patched']['source_revision_metadata'],
    historical_status=data['historical']['status'],default_admission=data['default_admission'],robot_actions=0)
args.out.with_suffix('.receipt.json').write_bytes((json.dumps(receipt,indent=2)+'\n').encode('utf-8'))
print(json.dumps(receipt,indent=2))
