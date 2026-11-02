"""Freeze the fixed replay from Git, retaining every historical evidence byte."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

repo=Path(r'C:\Users\fuker\Desktop\workspace\project-033-flexcell\code-clone')
root=Path(r'C:\Users\fuker\Documents\Codex\2026-10-30\https-github-com-yenefa-flexcell-https\work\portable-native-20261101')
def git(*args):
    return subprocess.check_output(['git','-C',str(repo),*args])
assert not git('status','--porcelain','--untracked-files=no').strip()
revision=git('rev-parse','HEAD').decode().strip()
preserved={}
for name in ('raw-evidence.zip','receipt.json','receipt-before-source-binding.json','source-binding.json'):
    path='setup/acceptance/native_audit_20261031/'+name
    old=git('show','b042f9b:'+path)
    current=(repo/path).read_bytes()
    assert old==current,name
    preserved[name]=hashlib.sha256(current).hexdigest()
paths=['setup/acceptance/native_audit_20261031','scripts/native_cycle_gate.py',
       'scripts/contact_gate.py','scripts/integrated_contact_gate.py',
       'src/flexcell/flexcell_skills/flexcell_skills/joint_follow.py',
       'src/flexcell/flexcell_skills/flexcell_skills/__init__.py']
archive=root/'fixed-lf-source.tar'
assert not archive.exists()
subprocess.run(['git','-C',str(repo),'archive','--format=tar','--output',str(archive),revision,*paths],check=True)
tree=root/'lf-patched'; tree.mkdir()
with tarfile.open(archive) as bundle:
    assert bundle.pax_headers['comment']==revision
    for member in bundle:
        destination=tree/member.name
        assert destination.resolve().is_relative_to(tree.resolve())
        if member.isdir(): destination.mkdir(parents=True,exist_ok=True)
        else:
            assert member.isfile()
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(bundle.extractfile(member).read())
for name in paths[1:]:
    assert b'\r\n' not in (tree/name).read_bytes(),name
(root/'fixed-source-revision.txt').write_bytes((revision+'\n').encode('ascii'))
report=dict(source_revision=revision,archive_bytes=archive.stat().st_size,
    archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),preserved_files=preserved,
    canonical_gate_files=4,checkout_policy='unmodified Git archive LF bytes',robot_actions=0)
(root/'fixed-source.json').write_bytes((json.dumps(report,indent=2)+'\n').encode('utf-8'))
print(json.dumps(report,indent=2))
