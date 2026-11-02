"""Package completed raw evidence and verify every member against its source."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

root=Path('/home/ros/agentic_workcell_ws/artifacts/preposition-world-20261031')
repo=Path('/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/code-clone')
chat=Path('/mnt/c/Users/fuker/Documents/Codex/2026-10-30/https-github-com-yenefa-flexcell-https')
capsule=repo/'setup/acceptance/preposition_world_20261031'
window=json.loads((root/'joint-window/window.json').read_text())
assert window['status']=='FUNCTIONAL_WINDOW_PASS' and len(window['episodes'])==1
proc=subprocess.run(['pgrep','-af','[g]z sim|[m]ove_group|[m]tc_planner|[c]arry_server|[r]ecord_sim_data'],text=True,capture_output=True)
assert proc.returncode==1,proc.stdout
old=Path('/home/ros/agentic_workcell_ws')
patch=subprocess.check_output(['git','-C',str(old),'-c','core.filemode=false','diff','--binary'],stderr=subprocess.DEVNULL)
before=json.loads((root/'old-wsl-preflight.json').read_text())
assert hashlib.sha256(patch).hexdigest()==before['dirty_patch_sha256']
entries=[('window/'+str(path.relative_to(root/'joint-window')),path)
         for path in sorted((root/'joint-window').rglob('*')) if path.is_file()]
preflight=['identity-before.json','runtime-stages.tsv','source-revision.txt','source.tar.sha256',
           'locked-upstream.json','dependency-packages.tsv','frozen-runtime-runner.sh']
entries.extend(('preflight/'+name,root/name) for name in preflight)
target=capsule/'raw-window.zip'
hashes={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in entries}
with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
    for name,path in entries: bundle.write(path,name)
with zipfile.ZipFile(target) as bundle:
    assert bundle.testzip() is None
    for name,path in entries:
        assert hashlib.sha256(bundle.read(name)).hexdigest()==hashes[name]
        assert hashlib.sha256(path.read_bytes()).hexdigest()==hashes[name]
receipt=dict(source_revision=(root/'source-revision.txt').read_text().strip(),
             archive_sha256=hashlib.sha256(target.read_bytes()).hexdigest(), archive_bytes=target.stat().st_size,
             archive_members=len(entries), byte_verified_members=len(entries), files=hashes,
             window_id=window['window_id'], no_replacements=True, remaining_runtime_processes=0,
             old_wsl_dirty_patch_unchanged=True, default_admission='NO_GO')
(capsule/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
for name in ['red.log','green.log','test-result.log','static-scan.log','build.log','upstream-build.log',
             'tests-first-layout-error.log']:
    shutil.copyfile(root/name,capsule/name)
shutil.copyfile(root/'parity-counterexamples/counterexamples.json',capsule/'parity-counterexamples.json')
for name in ['preposition-world-preflight.py','preposition-world-build-locked.sh','preposition-world-upstream.py',
             'preposition-world-tests.sh','preposition-world-sim.sh','preposition-world-package.py',
             'parity-junior-counterexamples.py']:
    shutil.copyfile(chat/'work'/name,capsule/name)
shutil.copyfile(target,chat/'outputs/FlexCell-预定位几何修复原始证据-20261031.zip')
assert hashlib.sha256((chat/'outputs/FlexCell-预定位几何修复原始证据-20261031.zip').read_bytes()).hexdigest()==receipt['archive_sha256']
print(json.dumps({k:v for k,v in receipt.items() if k!='files'},indent=2))
