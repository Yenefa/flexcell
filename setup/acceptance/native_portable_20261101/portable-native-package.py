"""Preserve the old source observations and archive the independent LF proofs."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

repo=Path(r'C:\Users\fuker\Desktop\workspace\project-033-flexcell\code-clone')
work=Path(r'C:\Users\fuker\Documents\Codex\2026-10-30\https-github-com-yenefa-flexcell-https\work')
root=work/'portable-native-20261101'
capsule=repo/'setup/acceptance/native_portable_20261101'
capsule.mkdir(exist_ok=False)
names=['preflight.json','old-lf-replay.stdout','old-lf-replay.stderr','fixed-source.json',
    'fixed-source-revision.txt','red.log','red.xml','targeted-green.log','targeted-green.xml',
    'full-pytest.log','full-pytest.xml','static-scan.log','replay-linux-lf.json',
    'replay-linux-lf.receipt.json','replay-linux-lf.stderr','replay-windows-lf-corrected.json',
    'replay-windows-lf-corrected.receipt.json','replay-windows-lf-corrected.stderr',
    'replay-windows-lf.json','replay-windows-lf.stderr','legacy-review.json','legacy-review-source.tar']
for name in names:
    shutil.copyfile(root/name,capsule/name)
for name in ('portable-native-preflight.py','portable-native-tests.sh','portable-native-green.sh',
             'portable-native-freeze.py','portable-native-run.py','portable-native-linux.sh',
             'legacy-matrix-review.py','portable-native-package.py'):
    shutil.copyfile(work/name,capsule/name)
old=subprocess.check_output(['git','-C',str(repo),'show',
    'b042f9b:setup/acceptance/native_audit_20261031/verify.py'])
(capsule/'verifier-before-portable-fix.py').write_bytes(old)
for name in ('replay-linux-lf.receipt.json','replay-windows-lf-corrected.receipt.json'):
    check=json.loads((capsule/name).read_text())
    assert check['exit_code']==0 and check['isolated'] and not check['site_packages']
    assert check['canonical_gate_files']==4 and check['robot_actions']==0
freeze=json.loads((capsule/'fixed-source.json').read_text())
for name,digest in freeze['preserved_files'].items():
    assert hashlib.sha256((repo/'setup/acceptance/native_audit_20261031'/name).read_bytes()).hexdigest()==digest
files={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in capsule.iterdir() if path.is_file()}
receipt=dict(schema_version=1,correction_source_revision=freeze['source_revision'],
    original_source_revision='b042f9b3a5178e915e906873b189f928641e4a8c',
    source_export_sha256=freeze['archive_sha256'],files=files,
    preserved_original_files=freeze['preserved_files'],canonical_text_policy='CRLF_PAIRS_TO_LF_ONLY',
    tests=dict(portability_cases=35,red_failed=25,red_passed=10,targeted_passed=50,
               full_python_passed=742,existing_fork_warnings=3,static_files=40,static_issues=0),
    independent_git_lf_replay=dict(windows='PASS',linux='PASS',site_packages=False),
    historical_revision_metadata='INVALID_TRAILING_CR',historical_ci_stale_cause='UNKNOWN',
    historical_ci_status='STOPPED',robot_actions=0,default_admission='NO_GO')
(capsule/'receipt.json').write_bytes((json.dumps(receipt,indent=2)+'\n').encode('utf-8'))
print(json.dumps({k:v for k,v in receipt.items() if k!='files'},indent=2))
