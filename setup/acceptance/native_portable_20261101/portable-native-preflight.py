"""Reproduce the source-binding failure from committed LF bytes, offline."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile

repo=Path(r'C:\Users\fuker\Desktop\workspace\project-033-flexcell\code-clone')
root=Path(r'C:\Users\fuker\Documents\Codex\2026-10-30\https-github-com-yenefa-flexcell-https\work\portable-native-20261101')
root.mkdir(exist_ok=False)
revision=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
paths=['setup/acceptance/native_audit_20261031','scripts/native_cycle_gate.py',
       'scripts/contact_gate.py','scripts/integrated_contact_gate.py',
       'src/flexcell/flexcell_skills/flexcell_skills/joint_follow.py',
       'src/flexcell/flexcell_skills/flexcell_skills/__init__.py']
archive=root/'lf-source.tar'
subprocess.run(['git','-C',str(repo),'archive','--format=tar','--output',str(archive),revision,*paths],check=True)
tree=root/'lf-source'; tree.mkdir()
with tarfile.open(archive) as bundle:
    assert bundle.pax_headers['comment']==revision
    for member in bundle:
        destination=tree/member.name
        assert destination.resolve().is_relative_to(tree.resolve())
        if member.isdir(): destination.mkdir(parents=True,exist_ok=True)
        else:
            assert member.isfile(),member.name
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(bundle.extractfile(member).read())
capsule=tree/'setup/acceptance/native_audit_20261031'
receipt=json.loads((capsule/'receipt.json').read_text())
binding=json.loads((capsule/'source-binding.json').read_text())
comparison={}
sha=lambda data:hashlib.sha256(data).hexdigest()
for path,recorded in receipt['verification_sources'].items():
    data=(tree/path).read_bytes()
    comparison[path]=dict(recorded_sha256=recorded,committed_sha256=sha(data),
        lf_matches_recorded=sha(data)==recorded,
        crlf_matches_recorded=sha(data.replace(b'\n',b'\r\n'))==recorded,
        runtime_source_matches_git=binding['source_files'][path]==sha(data))
replay=subprocess.run([sys.executable,'-I','-S','-B',str(capsule/'verify.py')],cwd=tree,
    capture_output=True,text=True,encoding='utf-8')
(root/'old-lf-replay.stdout').write_bytes(replay.stdout.encode('utf-8'))
(root/'old-lf-replay.stderr').write_bytes(replay.stderr.encode('utf-8'))
assert replay.returncode==1 and 'gate changed' in replay.stderr
assert 'scripts/contact_gate.py' in replay.stderr
report=dict(source_revision=revision,exit_code=replay.returncode,comparison=comparison,
    raw_zip_sha256=sha((capsule/'raw-evidence.zip').read_bytes()),
    result='LF_CHECKOUT_FAILURE_REPRODUCED',robot_actions=0)
(root/'preflight.json').write_bytes((json.dumps(report,indent=2)+'\n').encode('utf-8'))
print(json.dumps(report,indent=2))
