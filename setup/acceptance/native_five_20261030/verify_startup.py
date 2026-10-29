#!/usr/bin/env python3
"""Retain the pre-cycle startup stop; it cannot be counted as five cycles."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
from contact_gate import observation, require


def verify():
    path=Path(__file__).with_name('startup_6c3d87b.zip')
    require(hashlib.sha256(path.read_bytes()).hexdigest() ==
            'ebe3b7f3de0106752bd78799959db30ff9a05706735d0032a1ae2796f63a713a','startup archive changed')
    with zipfile.ZipFile(path) as z:
        require(len(z.namelist())==19 and not any(n.endswith(('worker.json','native-events.jsonl','recorder.log'))
                or n.startswith('data/') for n in z.namelist()),'startup stop contains a dispatched fixture')
        result=json.loads(z.read('result.json'));identity=json.loads(z.read('identity.stdout'))
        require(result['status']=='STOPPED' and result['error']=="ValueError('contact evidence: native stream stale')" and
                result['robot_motion_tasks']==0 and result['owned_exit']==0 and 'worker_exit' not in result and
                'recorder_exit' not in result,'startup terminal changed')
        require(identity['source_revision']=='6c3d87b7c3964d7dcd6f6124e8ca0e4e34a42968' and
                not identity['mismatches'],'startup source/install identity changed')
        require(result['declaration_sha256']==hashlib.sha256(z.read('declaration.json')).hexdigest() and
                result['world_sha256']==hashlib.sha256(z.read('world.sdf')).hexdigest(),'startup declaration changed')
        loaded=json.loads(z.read('loaded_libraries.json'))
        for name in ('flexcell_physics_trace','flexcell_contact_trace','flexcell_detachable_carry'):
            require(any(name in p and sha==identity['native_libraries']['lib/lib'+name+'.so'] for p,sha in loaded.items()),
                    'startup actually loaded native library differs')
        physics=[json.loads(l) for l in z.read('physics_steps.jsonl').splitlines()]
        contacts=[json.loads(l) for l in z.read('contact_steps.jsonl').splitlines()]
        require(len(physics)==len(contacts)==7062,'startup raw count changed')
        for rows in (physics,contacts):
            require(all(b['sim_ns']-a['sim_ns']==2_000_000 and b['monotonic_ns']>a['monotonic_ns']
                        for a,b in zip(rows,rows[1:])),'startup raw clock incomplete')
        for row in contacts:
            for target in row['targets'].values(): observation(target)
    return dict(status='STARTUP_STOP_RETAINED',source_revision=identity['source_revision'],
                qualification_cycles_dispatched=0,raw_samples_per_stream=7062,default_admission='NO_GO')


if __name__=='__main__': print(json.dumps(verify(),indent=2))
