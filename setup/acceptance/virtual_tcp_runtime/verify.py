#!/usr/bin/env python3
"""Recompute the complete one-task window; optionally audit native CDR handoff."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
import yaml

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src/flexcell/flexcell_skills')]


def wire_handoff(run):
    from rclpy.serialization import deserialize_message,serialize_message
    from flexcell_interfaces.srv import PlanManipulation
    from moveit_msgs.msg import PlanningScene
    from rcl_interfaces.msg import ParameterEvent
    requests={}
    for folder in (run/'mtc_plans').iterdir():
        q=deserialize_message((folder/'request.cdr').read_bytes(),PlanManipulation.Request)
        r=deserialize_message((folder/'response.cdr').read_bytes(),PlanManipulation.Response)
        scene=deserialize_message((folder/'scene.cdr').read_bytes(),PlanningScene)
        params=deserialize_message((folder/'parameters.cdr').read_bytes(),ParameterEvent)
        assert q.operation not in requests
        requests[q.operation]=(q,r,scene,params,folder)
        assert r.success and len(r.trajectories)==len(r.executor_targets)==len(q.targets)==3
        skill=json.loads((run/('skills/'+q.operation.lower()+'.jsonl')).read_text())
        motions={v['request_id']:v for v in map(json.loads,(run/'skills/move_to_pose.jsonl').read_text().splitlines())}
        for i,stage in enumerate(skill['mtc_stages']):
            trajectory=r.trajectories[i]
            assert stage['trajectory_sha256']==hashlib.sha256(serialize_message(trajectory)).hexdigest()
            assert set(trajectory.joint_trajectory.joint_names)=={'joint1','joint2','joint3','joint4'}
            endpoint=r.executor_targets[i].pose.position
            expected=[endpoint.x,endpoint.y,endpoint.z]
            logical=q.targets[i].pose.position
            assert stage['target']==[logical.x,logical.y,logical.z]
            if q.operation=='PLACE': assert stage['executor_target']==expected
            assert motions[stage['request_id']]['target']['position']==stage['executor_target']
            assert motions[stage['request_id']]['outcome']=='SUCCEEDED'
    assert set(requests)=={'PICK','PLACE'}
    q,r,scene,params,folder=requests['PLACE']
    assert q.attached_object_targets and not requests['PICK'][0].attached_object_targets
    assert q.targets[1].pose.position.z==.0675
    original=next(p.value.string_value for p in params.changed_parameters if p.name=='robot_description')
    assert ET.fromstring(original).find("link[@name='flexcell_object_tcp']") is None
    robot=ET.parse(folder/'planning_model.urdf').getroot()
    assert robot.find("joint[@name='flexcell_object_tcp_joint']").get('type')=='fixed'
    assert robot.find("link[@name='flexcell_object_tcp']/collision") is None
    assert any(b.object.id=='target_box_a' for b in scene.robot_state.attached_collision_objects)
    place=json.loads((run/'skills/place.jsonl').read_text())
    target=q.targets[1].pose.position
    assert math.isclose(math.dist(place['object_before_release'][:3],[target.x,target.y,target.z]),place['release_target_error_m'],abs_tol=1e-12)
    return dict(planning_records=2,trajectories_matched=6,physical_model_unchanged=True)


def verify(wire=False):
    from joint_follow_gate import verify_run as follow_gate
    from integrated_contact_gate import verify_run as contact_gate
    root=Path(__file__).resolve().parent
    receipt=json.loads((root/'receipt.json').read_text());archive=root/'window_5196568.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==receipt['archive_sha256']=='935e8602b84575f7ad60fdaa4fd9ded790ac0ade3b32543fe77772203b39abf8'
    with tempfile.TemporaryDirectory(prefix='virtual-tcp-replay-') as tmp,zipfile.ZipFile(archive) as z:
        assert len(z.namelist())==len(set(z.namelist()))==len(receipt['files'])==53
        assert set(z.namelist())==set(receipt['files'])
        for name,digest in receipt['files'].items():
            assert not Path(name).is_absolute() and '..' not in Path(name).parts
            assert hashlib.sha256(z.read(name)).hexdigest()==digest
        z.extractall(tmp)
        folder=Path(tmp);window=json.loads((folder/'window.json').read_text())
        assert window['status']=='FUNCTIONAL_WINDOW_PASS' and window['no_replacements'] is True and len(window['episodes'])==1
        run,=(folder/'trial-01').glob('run-*');result=json.loads((run/'result.json').read_text())
        assert result['status']=='PASS' and result['physical_tasks_dispatched']==1
        assert result['task']['fsm_trace']==['PICK_A(attempt=1):OK','PLACE_A:OK','VERIFY_A(attempt=1):OK']
        assert result['owned_launch_exit']==result['recorder_exit']==0 and result['native_identity_verified_before_dispatch'] is True
        declaration=json.loads((folder/'declaration.json').read_text())
        config=yaml.safe_load((run/'params.yaml').read_text())
        assert config['task_fsm_server']['ros__parameters']['recovery_budget']==0
        assert config['place_server']['ros__parameters']['place_tolerance_m']==.06
        assert hashlib.sha256((run/'world.sdf').read_bytes()).hexdigest()==declaration['world_sha256']
        follow=follow_gate(run,'target_box_a',min_duration_s=10.,physics_step_ns=2_000_000)
        contact=contact_gate(run,'target_box_a',declaration)
        assert follow==window['episodes'][0]['follow_evidence'] and contact==window['episodes'][0]['contact_evidence']
        identity=json.loads((run/'identity.stdout').read_text())
        assert identity['source_revision']==receipt['source_revision']=='519656878ebe196e13bccbc696b2bfb942bb8d90' and identity['mismatches']==[]
        mapping=json.loads((run/'runtime_native_mapping.json').read_text())
        for name in ['mtc_planner','libflexcell_physics_trace.so','libflexcell_contact_trace.so','libflexcell_detachable_carry.so']:
            a=[h for p,h in mapping.items() if Path(p).name==name];b=[h for p,h in identity['native_libraries'].items() if Path(p).name==name]
            assert len(a)==len(b)==1 and a==b
        health=json.loads((run/'health_after.stdout').read_text())
        assert health['ok'] and health['hard_fail']==[] and len(health['checks'])==19
        assert health['checks']['task_state']=='IDLE' and health['checks']['carry_engaged'] is False
        place=json.loads((run/'skills/place.jsonl').read_text())
        assert place['release_target_error_m']<=.06 and place['place_error_m']<=.06
        answer=dict(status='VIRTUAL_TCP_TASK_REPRODUCED',tasks=1,final_error_m=result['task']['final_position_error_m'],
                    prerelease_error_m=place['release_target_error_m'],follow_sim_s=follow['attached_duration_s'],
                    joined_steps=contact['joined_steps'],default_admission='NO_GO')
        if wire:answer['wire_handoff']=wire_handoff(run)
        return answer


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--wire',action='store_true')
    print(json.dumps(verify(parser.parse_args().wire),indent=2))
