"""One fixed Runtime task window. No retries or favourable replacement trials."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from prepare_model import prepare

ROOT=Path('/candidate')
FROZEN={
    'benchmark/evaluators/evaluate.py':'441903f15e50555311a9ead9c1426689ad4799294fdc51750c8e276b36279654',
    'benchmark/evaluators/sealed_evaluate.py':'fa330e69ac6a35aec4b1313638b458885e93c8877ea5dc53f642859783e3acad',
    'benchmark/evaluators/observe_from_run.py':'c9b910cde2b93da9c5dae1760c1e731d7679eb20b52b3b5fc19b9028973c5250',
    'benchmark/evaluators/capture_ground_truth.py':'faec24ae921acdbef25114fbd20e7c435453fd8d7bdf8190f9cacecbd59cb608',
    'benchmark/schemas/taskspec.schema.json':'29aae267b157efc2f91d48578ed849c4427e79b629cb3fdea7f892dc7a57563e',
    'benchmark/generators/generate.py':'5c1324db5d7156c4f94b9e5725be07722931b3ad90106cc055513d9236140cb2',
    'benchmark/generators/seal_held_out.py':'b4c63360db75a603e798e44a614baeedde0e5086b0f4aae2be65355e98d53a8f',
    'benchmark/generators/unseen_tasks.py':'db646d1e02fd946a8f28d1e435f12eca012e9a74a5d72ffd324a956883dfb10f',
    'evolution/validation/regress.py':'a3d8bf5246a95695a37ddf0a25f2565b6198f2acc132f84ec1e3dbae7d107d9b',
    'src/flexcell/flexcell_skills/flexcell_skills/contracts/push.py':'e8a44c7d1b5889c786e8653759861f2ebefcccc1bec435bf2e439592d4945b53',
}


def main():
    out=Path('/artifacts');out.mkdir(exist_ok=True)
    hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FROZEN}
    (out/'frozen_integrity.json').write_text(json.dumps(hashes,indent=2))
    if hashes!=FROZEN:raise RuntimeError('frozen files or push arithmetic drifted')
    model=prepare(out/'model')
    metadata=dict(source_revision=os.environ.get('FLEXCELL_SOURCE_REV'),frozen_files=hashes,
        model=model,slots=[['legacy','CI_L0',180,'original'],['finger_tcp','CI_C1',181,'original'],
            ['finger_tcp','CI_C2',182,str(Path(__file__).with_name('probe_blue.json'))]],
        not_formal_held_out=True,model_calls=0,
        comparison_scope='same newly built image and task-scoped graph; do not pool prior local-image results')
    source_files=list((ROOT/'src/flexcell/flexcell_skills/flexcell_skills').glob('contact_*.py'))
    source_files+=[ROOT/'src/flexcell/flexcell_skills/flexcell_skills/task_fsm_server.py',
        ROOT/'runtime/planner/push_task.py',ROOT/'runtime/run_public_push_task.py',
        ROOT/'src/flexcell/flexcell_interfaces/action/ContactPush.action']
    metadata['sources']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    (out/'ci_preexecution.json').write_text(json.dumps(metadata,indent=2))
    results=[];candidate_passed=False
    try:
        for backend,label,domain,task in metadata['slots']:
            if label=='CI_C2' and not candidate_passed:
                results.append(dict(label=label,status='NOT_RUN',reason='original candidate task did not pass'));continue
            with (out/(label+'_driver.log')).open('x') as log:
                process=subprocess.run([sys.executable,str(Path(__file__).with_name('run_case.py')),
                    backend,label,str(domain),task],stdout=log,stderr=subprocess.STDOUT,timeout=900.)
            directory=out/label
            def read(name):
                try:return json.loads((directory/name).read_text())
                except (FileNotFoundError,ValueError):return None
            status=read('run_status.json');verdict=read('verdict.json');runtime=read('runtime/runtime_result.json')
            completed=(process.returncode==0 and status and status['status']=='EXECUTED' and runtime
                and runtime['agent_claimed_success'] is True and verdict and verdict['passed'] is True
                and len(verdict.get('evidence',{}).get('gates',[]))==9
                and all(g['ok'] for g in verdict['evidence']['gates']))
            row=dict(label=label,backend=backend,driver_exit=process.returncode,task_completed=bool(completed),
                status=status,independent_verdict=verdict,runtime=runtime)
            results.append(row)
            print('ACTUAL_RUNTIME_TASK_RESULT '+json.dumps(row),flush=True)
            if label=='CI_C1':candidate_passed=bool(completed)
    finally:
        payload=dict(kind='PUBLIC_RUNTIME_TASK_WINDOW',results=results,
            candidate_tasks_completed=sum(bool(r.get('task_completed')) for r in results if r['label'].startswith('CI_C')),
            raw_failures_retained=True,baseline_promoted=False)
        (out/'ci_results.json').write_text(json.dumps(payload,indent=2))
        print('ACTUAL_RUNTIME_WINDOW '+json.dumps(payload),flush=True)
        manifest={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in out.rglob('*') if p.is_file() and p.name!='SHA256_MANIFEST.json'}
        (out/'SHA256_MANIFEST.json').write_text(json.dumps(manifest,indent=2))
    return 0 if payload['candidate_tasks_completed']==2 else 2


if __name__=='__main__':raise SystemExit(main())
