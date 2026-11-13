"""Read-only raw replay of the fixed repeated physical task window."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src/flexcell/flexcell_skills'))
from flexcell_skills.contracts.contact_task import returned_component_ready

ARCHIVE_SHA256=json.loads(Path(__file__).with_name('archive.json').read_text())['sha256']


def verify(archive,out):
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==ARCHIVE_SHA256
    out.mkdir(exist_ok=False);raw=out/'raw';raw.mkdir()
    with zipfile.ZipFile(archive) as zipped:
        for name in zipped.namelist():
            if not (raw/name).resolve().is_relative_to(raw.resolve()):raise ValueError('invalid archive path')
        zipped.extractall(raw)
    manifest=json.loads((raw/'SHA256_MANIFEST.json').read_text())
    actual={str(p.relative_to(raw)) for p in raw.rglob('*') if p.is_file() and p.name!='SHA256_MANIFEST.json'}
    assert actual==set(manifest),'manifest coverage'
    for name,digest in manifest.items():assert hashlib.sha256((raw/name).read_bytes()).hexdigest()==digest,name
    preexecution=json.loads((raw/'preexecution.json').read_text())
    for name,digest in preexecution['sources'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    frozen=json.loads((raw/'frozen_integrity.json').read_text())
    for name,digest in frozen.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    result=dict(archive_sha256=ARCHIVE_SHA256,manifest_files=len(manifest),manifest_complete=True,
        all_hashes_match=True,frozen_files_and_push_core_match=True,physical_executions=0,cases=[])
    for label in ('RED_1','RED_2','RED_3','BLUE_1','BLUE_2'):
        case=raw/label;dest=out/label;dest.mkdir()
        original=json.loads((case/'verdict.json').read_text())
        if not (case/'gt_after.json').exists():
            result['cases'].append(dict(label=label,status='NO_FINAL_STATE'))
            continue
        task=(ROOT/'benchmark/tasks/t08_dev/T08-push-seed2000.json' if not label.startswith('BLUE')
              else ROOT/'setup/acceptance/evobot_runtime_push_20261112/probe_blue.json')
        spec=json.loads(task.read_text());target=next(iter(spec['expected_goal']['push']))
        protected=[o['name'] for o in spec['objects'] if o['name']!=target];assert len(protected)==1
        provenance=json.loads((case/'provenance.json').read_text())
        assert hashlib.sha256(task.read_bytes()).hexdigest()==provenance['task_sha256']
        for old_path,digest in provenance['sources'].items():
            source=ROOT/old_path.removeprefix('/candidate/')
            assert hashlib.sha256(source.read_bytes()).hexdigest()==digest,old_path
        links=['open_manipulator_x::%s::%s_collision'%(name,name)
               for name in ('link5','gripper_left_link','gripper_right_link')]
        command=[sys.executable,str(ROOT/'benchmark/evidence/recorder.py'),
            '--physics-log',str(case/'physics.jsonl'),'--contact-log',str(case/'contacts.jsonl'),
            '--joint-log',str(case/'joints.jsonl'),'--task',str(task),'--task-id',spec['task_id'],
            '--run-id','runtime-'+label,'--target',target,'--protected',protected[0],
            '--rest-height',str(next(o['initial_pose'][2] for o in spec['objects'] if o['name']==target)),
            '--pusher-links',*links,'--gripper-joint','gripper_left_joint','--out',str(dest/'bundle.json')]
        with (dest/'recorder.log').open('x') as log:
            recorded=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
        bundle=json.loads((dest/'bundle.json').read_text())
        final=json.loads((case/'gt_after.json').read_text());runtime=json.loads((case/'runtime/runtime_result.json').read_text())
        final['evidence']=bundle
        final['trajectory']={name:dict(max_z_m=max(s[5] for s in row['samples']))
                             for name,row in bundle['objects'].items() if row['samples']}
        final['agent_claimed_success']=runtime['agent_claimed_success']
        (dest/'observation.json').write_text(json.dumps(final))
        with (dest/'verdict.json').open('x') as log:
            subprocess.run([sys.executable,str(ROOT/'benchmark/evaluators/evaluate.py'),str(task),
                str(dest/'observation.json')],check=True,stdout=log)
        verdict=json.loads((dest/'verdict.json').read_text());components=[]
        for path in (case/'sim/skills/composites').glob('*.jsonl'):
            components.extend(row['component'] for row in map(json.loads,path.read_text().splitlines())
                              if row['event']=='NATIVE_TERMINAL')
        entry=dict(label=label,recorder_exit=recorded.returncode,
            recorder_summary=(dest/'recorder.log').read_text().strip(),verdict=verdict,runtime=runtime,
            returned_components=[dict(request_id=c['request_id'],goal_uuid=c['goal_uuid'],
                ready_at_recorded_consumption=returned_component_ready(c),
                receipt_age_s=c['receipt_age_s'],motion_goals_used=c['motion_goals_used'],
                returned_displacement_m=c['displacement_m']) for c in components if c.get('backend')=='finger_tcp'])
        assert verdict['passed']==original['passed'],label
        if original['passed'] is True:
            assert recorded.returncode==0 and verdict['passed'] and not verdict['false_success'],label
            assert len(verdict['evidence']['gates'])==9 and all(g['ok'] for g in verdict['evidence']['gates']),label
            assert len(entry['returned_components'])==2 and all(c['ready_at_recorded_consumption'] for c in entry['returned_components']),label
        result['cases'].append(entry)
    result['ordinary_regressions']={}
    for label in ('REG_NORMAL','REG_DUAL'):
        paths=list((raw/label).glob('run-*/result.json'))
        assert len(paths)==1,label
        value=json.loads(paths[0].read_text())
        assert value['case']==('normal' if label=='REG_NORMAL' else 'dual_object'),label
        result['ordinary_regressions'][label]=value
    (out/'verification.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(dict(manifest_files=len(manifest),all_hashes_match=True,
        cases=[dict(label=c['label'],passed=c['verdict']['passed'],recorder_exit=c['recorder_exit']) for c in result['cases']])))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path);parser.add_argument('out',type=Path)
    args=parser.parse_args();verify(args.archive,args.out)
