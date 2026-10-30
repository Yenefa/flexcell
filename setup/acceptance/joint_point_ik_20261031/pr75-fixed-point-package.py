"""Package only completed, byte-verified local evidence; never modify raw logs."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

root=Path('/home/ros/agentic_workcell_ws/artifacts/joint-point-runtime-20261031')
numeric=Path('/home/ros/agentic_workcell_ws/artifacts/joint-point-fix-20261031')
win=Path('/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/code-clone')
chat=Path('/mnt/c/Users/fuker/Documents/Codex/2026-10-30/https-github-com-yenefa-flexcell-https')
audit=json.loads((root/'local-audit.json').read_text())
assert audit['remaining_runtime_processes']==0
dependency=json.loads((numeric/'dependency-check/receipt.json').read_text())
patch=subprocess.check_output(['git','-C','/home/ros/agentic_workcell_ws','diff',
                               audit['source_revision'],dependency['final_code_revision']],text=True)
(numeric/'dependency-check/post-run-dependency.patch').write_text(patch)
for path, expected in audit['files'].items():
    assert hashlib.sha256((root/path).read_bytes()).hexdigest()==expected,path
target=chat/'outputs/FlexCell-Joint修复本机验证-20261031.zip'
scripts=['pr75-point-trace-green.sh','pr75-point-verify.sh','pr75-fixed-point-sim.sh',
         'pr75-fixed-point-audit.py','pr75-fixed-point-package.py','pr75-fixed-point-fk.py','pr75-fixed-point-post.sh',
         'pr75-point-dependency-check.sh']
entries=[]
for prefix,directory in [('runtime',root),('numerical',numeric)]:
    entries.extend((prefix+'/'+str(path.relative_to(directory)),path) for path in sorted(directory.rglob('*'))
                   if path.is_file() and not path.is_symlink())
entries.extend(('tools/'+name,chat/'work'/name) for name in scripts)
with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for name,path in entries: archive.write(path,name)
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    for name,path in entries:
        assert hashlib.sha256(archive.read(name)).digest()==hashlib.sha256(path.read_bytes()).digest(),name
receipt=dict(source_revision=audit['source_revision'], archive=str(target),
             final_code_revision=dependency['final_code_revision'], native_binary_unchanged=dependency['native_binary_unchanged'],
             archive_sha256=hashlib.sha256(target.read_bytes()).hexdigest(), archive_bytes=target.stat().st_size,
             archive_members=len(entries), byte_verified_members=len(entries),
             core_status=audit['core_status'], joint_status=audit['joint']['window_status'],
             remaining_runtime_processes=0, no_replacement_windows=True,
             stages_tsv=(root/'stages.tsv').read_text())
capsule=win/'setup/acceptance/joint_point_ik_20261031'
capsule.mkdir(exist_ok=False)
(capsule/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
for name in ('local-audit.json','planner-fk-audit.json'):
    shutil.copyfile(root/name,capsule/name)
shutil.copyfile(root/'local-audit.json',chat/'outputs/FlexCell-Joint修复运行审计-20261031.json')
for name in scripts:
    shutil.copyfile(chat/'work'/name,capsule/name)
for name in ('test-result-all.log','static-scan.log','build-all.log'):
    shutil.copyfile(numeric/'verification-v2'/name,capsule/name)
for name in ('test-result.log','receipt.json','package-graph.tsv','post-run-dependency.patch'):
    shutil.copyfile(numeric/'dependency-check'/name,capsule/('dependency-'+name))
print(json.dumps(receipt,indent=2))
