#!/usr/bin/env python3
"""Reproduce all five native cycles from the complete preserved raw files."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import tempfile
import zipfile
import yaml

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src/flexcell/flexcell_skills')]
from native_cycle_gate import verify_run


def require(value,message):
    if not value: raise ValueError(message)


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''): h.update(chunk)
    return h.hexdigest()


def verify():
    retained=Path(__file__).resolve().parent;receipt_path=retained/'receipt.json'
    require(digest(receipt_path)=='efb3a0ed1321aa6b7e15c8c7a094877511be7bf20a0d413a38553ca2fc1641c9','five-cycle receipt changed')
    receipt=json.loads(receipt_path.read_text());archive=retained/'cycles_858f01a.zip'
    require(digest(archive)==receipt['archive_sha256'],'five-cycle archive changed')
    with tempfile.TemporaryDirectory(prefix='flexcell-native-five-audit-') as temporary:
        run=Path(temporary)
        with zipfile.ZipFile(archive) as z:
            names=z.namelist()
            require(len(names)==len(set(names)) and set(names)==set(receipt['files_sha256']) and
                    all(not PurePosixPath(n).is_absolute() and '..' not in PurePosixPath(n).parts for n in names),
                    'five-cycle archive members changed')
            z.extractall(run)
        for name,sha in receipt['files_sha256'].items():
            require(digest(run/name)==sha,'original native file changed: '+name)
        result=json.loads((run/'result.json').read_text());declaration=json.loads((run/'declaration.json').read_text())
        identity=json.loads((run/'identity.stdout').read_text())
        require(result['status']=='PASS' and result['worker_exit']==result['recorder_exit']==result['owned_exit']==0 and
                result['robot_motion_tasks']==0 and result['max_cycles']==5 and result['no_replacements'] is True,
                'native terminal or task scope changed')
        require(identity['source_revision']==receipt['source_revision']=='858f01a352ca503dd2540102887e33cbd7d089f6' and
                identity['source_tree_sha256']==receipt['source_tree_sha256'] and identity['mismatches']==[],
                'native source/install identity changed')
        require(result['declaration_sha256']==receipt['declaration_sha256']==digest(run/'declaration.json') and
                result['world_sha256']==declaration['world_sha256']==digest(run/'world.sdf'), 'declared world changed')
        loaded=json.loads((run/'loaded_libraries.json').read_text())
        for name in ('flexcell_physics_trace','flexcell_contact_trace','flexcell_detachable_carry'):
            require(any(name in p and h==identity['native_libraries']['lib/lib'+name+'.so'] for p,h in loaded.items()),
                    'native actually loaded observer/guard differs')
        require(any('dartsim' in p for p in loaded),'native engine identity absent')
        semantic=yaml.safe_load((run/'params.yaml').read_text())
        for node in semantic.values():
            for key in ('log_dir','episode_dir'):
                if key in node.get('ros__parameters',{}): node['ros__parameters'][key]='$RUN/'+key
        require(hashlib.sha256(json.dumps(semantic,sort_keys=True).encode()).hexdigest()==declaration['semantic_config_sha256'],
                'native semantic configuration changed')
        fingerprint=hashlib.sha256(json.dumps(dict(identity=identity,declaration=declaration,config=semantic),sort_keys=True).encode()).hexdigest()
        require(fingerprint==result['runtime_fingerprint']==receipt['runtime_fingerprint'],'native runtime fingerprint changed')
        for name in ('health_after_cycles.stdout','health_after.stdout'):
            health=json.loads((run/name).read_text())
            require(health['ok'] is True and not health['hard_fail'] and len(health['checks'])==19 and
                    health['checks']['task_state']=='IDLE' and health['checks']['carry_engaged'] is False,
                    'post-cycle or final health differs')
        collection=json.loads((run/'data/collection.json').read_text())
        require(collection['errors']==[] and collection['rosbag_exit']==0,'native joint-state recorder failed')
        evidence=verify_run(run,declaration)
        require(evidence==result['evidence'] and evidence['moving_parent_follow_qualified'] is False and
                evidence['default_admission']=='NO_GO','independent five-cycle result differs')
        return dict(status='FIVE_NATIVE_CYCLES_REPRODUCED',source_revision=receipt['source_revision'],
                    evidence=evidence,default_admission='NO_GO')


if __name__=='__main__': print(json.dumps(verify(),indent=2,allow_nan=False))
