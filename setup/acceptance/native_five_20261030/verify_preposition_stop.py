#!/usr/bin/env python3
"""Retain the epoch-selection stop: one preposition, zero engage requests."""
import hashlib
import json
import math
from pathlib import Path
import zipfile


def require(value,message):
    if not value: raise ValueError(message)


def verify():
    path=Path(__file__).with_name('preposition_225a885.zip')
    require(hashlib.sha256(path.read_bytes()).hexdigest()==
        'd837fffeb609f53d127567b4fbd14dae2f2f5947344ea88dbf040c0c03c32aa9','preposition stop archive changed')
    with zipfile.ZipFile(path) as z:
        result=json.loads(z.read('result.json'));worker=json.loads(z.read('worker.json'))
        require(result['status']=='STOPPED' and result['worker_exit']==1 and result['recorder_exit']==0 and
                result['owned_exit']==0,'preposition stop terminal changed')
        require(worker['status']=='STOPPED' and worker['error']==
            "ValueError('contact evidence: native stream stale; age_ns=2668183423')" and
            len(worker['cycles'])==1 and 'reference_sim_ns' not in worker['cycles'][0], 'epoch stop was reclassified')
        events=[json.loads(l) for l in z.read('native-events.jsonl').splitlines()]
        require([r['label'] for r in events]==['initial_status','before_preposition','preposition'] and
                all(r['transport_ok'] is True for r in events) and events[-1]['reply'] is True and
                events[-1]['operation']=='set_pose' and events[-1]['object']=='target_box_a',
                'fixture proceeded after the epoch stop')
        identity=json.loads(z.read('identity.stdout'))
        require(identity['source_revision']=='225a8851cb320b6a3adff917cfc4c138e2ae46f3' and
                identity['mismatches']==[], 'preposition source/install identity changed')
        physics=[json.loads(l) for l in z.read('physics_steps.jsonl').splitlines()]
        after=[p for p in physics if p['monotonic_ns']>=events[-1]['request_mono_ns']]
        require(after and all(all(p['objects'][n]['joint_component'] is False for n in ('target_box_a','target_box_b'))
                for p in after),'attachment appeared without engage')
        require(any(math.dist(p['objects']['target_box_a']['pose'][:3],[.35,.18,.22])<.005 for p in after),
                'detached preposition was not physically observed')
        require(not any(n.startswith('reset_after') or n.startswith('health_after') for n in z.namelist()),
                'reset/cleanup occurred after the stopped fixture')
    return dict(status='PREPOSITION_STOP_RETAINED',cycle_attempts=1,prepositions=1,engage_requests=0,
                completed_cycles=0,default_admission='NO_GO')


if __name__=='__main__': print(json.dumps(verify(),indent=2))
