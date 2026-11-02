"""Read committed #86 receipts and reproduce its host/container path blind spot."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

repo=Path(r'C:\Users\fuker\Desktop\workspace\project-033-flexcell\code-clone')
root=Path(r'C:\Users\fuker\Documents\Codex\2026-10-30\https-github-com-yenefa-flexcell-https\work\portable-native-20261101')
revision=subprocess.check_output(['git','-C',str(repo),'rev-parse','origin/test/legacy-skill-matrix'],text=True).strip()
tree=root/'legacy-review-source'; tree.mkdir()
archive=root/'legacy-review-source.tar'
subprocess.run(['git','-C',str(repo),'archive','--format=tar','--output',str(archive),revision,
    'scripts/parity_report.py','scripts/contact_gate.py',
    'setup/acceptance/legacy_skill_matrix_20261031','setup/acceptance/legacy_parity_20261031'],check=True)
with tarfile.open(archive) as bundle:
    for member in bundle:
        destination=tree/member.name
        assert destination.resolve().is_relative_to(tree.resolve())
        if member.isdir(): destination.mkdir(parents=True,exist_ok=True)
        else:
            assert member.isfile()
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(bundle.extractfile(member).read())
summary={}
windows={}
for skill,prefix in [('mtc','legacy_parity_20261031'),('legacy','legacy_skill_matrix_20261031')]:
    for backend in ('teleport','detachable_joint'):
        directory=tree/'setup/acceptance'/prefix/backend
        window=json.loads((directory/'window.json').read_text())
        errors=[];tolerances=[]
        for item in window['episodes']:
            run=directory/Path(item['run']).name
            verify=run/'skills/verify.jsonl'
            if verify.exists():
                for row in map(json.loads,verify.read_text().splitlines()):
                    errors.append(row['position_error_m']);tolerances.append(row['tolerance_m'])
        assert len(errors)==5 and set(tolerances)=={.06}
        key=skill+'/'+backend
        summary[key]=dict(max_verified_error_m=max(errors),placements=len(errors),tolerance_m=.06,
            window_status=window['status'])
        windows[key]=(directory,window)
sys.path.insert(0,str(tree/'scripts'))
spec=importlib.util.spec_from_file_location('reviewed_parity',tree/'scripts/parity_report.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
paths=[]
for backend in ('teleport','detachable_joint'):
    directory,original=windows['legacy/'+backend]
    window=deepcopy(original)
    target=root/'host-layout'/('legacy-skill-'+backend)
    target.mkdir(parents=True)
    for index,item in enumerate(window['episodes']):
        run_name=Path(item['run']).name
        shutil.copytree(directory/run_name,target/('trial-%02d'%index)/run_name)
        item['run']='/artifacts/legacy-skill-'+backend+'/trial-%02d/'%index+run_name
        assert not Path(item['run']).exists()
    path=target/'window.json'
    path.write_bytes((json.dumps(window,indent=2)+'\n').encode('utf-8'))
    paths.append(path)
false_pass=module.compare(paths)
assert false_pass['status']=='CARRY_BACKEND_PARITY_PASS'
assert false_pass['declared_tolerance_m'] is None
assert all(v is None for v in false_pass['max_verified_error_m'].values())
assert all(not case['receipt'] for value in false_pass['table'].values() for case in value['cases'])
e=lambda skill,carry:summary[skill+'/'+carry]['max_verified_error_m']*1000
report=dict(source_revision=revision,committed_receipt_recalculation=summary,
    descriptive_maxima_differences_mm=dict(
        carry_at_mtc=e('mtc','detachable_joint')-e('mtc','teleport'),
        carry_at_legacy=e('legacy','detachable_joint')-e('legacy','teleport'),
        skill_at_teleport=e('legacy','teleport')-e('mtc','teleport'),
        skill_at_joint=e('legacy','detachable_joint')-e('mtc','detachable_joint')),
    attribution='These maxima do not identify a dominant causal error source; no statistical inference.',
    host_layout_reproduction=false_pass,result='HOST_RELOCATION_FALSE_PASS_REPRODUCED',
    missing_receipts=10,robot_actions=0)
(root/'legacy-review.json').write_bytes((json.dumps(report,indent=2)+'\n').encode('utf-8'))
print(json.dumps({k:v for k,v in report.items() if k!='host_layout_reproduction'},indent=2))
