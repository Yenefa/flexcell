#!/usr/bin/env python3
"""Read-only audit of the recorded software probe, without planning or motion."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile


def verify():
    root=Path(__file__).resolve().parent
    receipt=json.loads((root/'receipt.json').read_text())
    archive=root/'probe.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==receipt['archive_sha256']=='98e181a19febefbc113da1fd7a25aee3cc56c2b9435bbade04c472159601484c'
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist())==len(set(z.namelist()))==len(receipt['files'])==16
        assert set(z.namelist())==set(receipt['files'])
        for name,digest in receipt['files'].items(): assert hashlib.sha256(z.read(name)).hexdigest()==digest
        report=json.loads(z.read('report.json'))
        assert report==receipt['report'] and report['status']=='OFFLINE_TCP_PASS'
        assert report['robot_tasks']==0 and report['planned_stages']==3
        assert report['sampler_trials']==20 and report['legacy_valid_samples']==0 and report['tcp_valid_samples']==20
        assert report['tcp_max_error_m']<=1e-4 and report['blocked_valid_samples']==0 and report['collision_checks']>0
        assert report['bad_evidence_path_rejected'] and report['default_admission']=='NO_GO'
        urdf_name,=[p for p in z.namelist() if p.endswith('/planning_model.urdf')]
        srdf_name,=[p for p in z.namelist() if p.endswith('/planning_model.srdf')]
        robot=ET.fromstring(z.read(urdf_name));semantic=ET.fromstring(z.read(srdf_name))
        assert robot.find("joint[@name='flexcell_object_tcp_joint']").get('type')=='fixed'
        assert robot.find("link[@name='flexcell_object_tcp']/collision") is None
        group=semantic.find("group[@name='flexcell_object_arm']")
        assert group.find('group').get('name')=='arm' and group.find('joint').get('name')=='flexcell_object_tcp_joint'
        assert all(any(p.endswith('/'+name) and len(z.read(p))>0 for p in z.namelist()) for name in ['request.cdr','response.cdr','scene.cdr','parameters.cdr'])
    return dict(status='OFFLINE_TCP_EVIDENCE_VERIFIED',robot_tasks=0,default_admission='NO_GO')


if __name__=='__main__': print(json.dumps(verify(),indent=2))
