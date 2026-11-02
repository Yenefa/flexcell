#!/usr/bin/env python3
"""Retain the complete, rejected PLACE-planning window without replacement."""
import hashlib
import json
from pathlib import Path
import zipfile


def verify():
    archive = Path(__file__).with_name('window_c2583ae.zip')
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == 'd39c8dc1eab7bedd35e866d43511c505372bf00258de12a960ebf9a294691006'
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist()) == 36
        def read(suffix):
            names = [n for n in z.namelist() if n == suffix or n.endswith('/'+suffix)]
            assert len(names) == 1, suffix
            return z.read(names[0]).decode()
        window = json.loads(read('window.json'))
        assert window['status'] == 'STOPPED' and window['no_replacements'] is True
        assert len(window['episodes']) == 1
        result = window['episodes'][0]['result']
        assert result['status'] == 'ROBOT_FAILURE' and result['physical_tasks_dispatched'] == 1
        assert result['task']['fsm_trace'] == ['PICK_A(attempt=1):OK', 'PLACE_A:FAIL']
        assert result['native_identity_verified_before_dispatch'] is True
        pick = json.loads(read('skills/pick.jsonl'))
        place = json.loads(read('skills/place.jsonl'))
        assert str(pick['outcome']) == '0' and pick['error_code'] == 0
        assert str(place['outcome']) == '1' and place['error_code'] == 30
        assert place['planning_target_reference'] == 'attached_box_center'
        assert 'hover (0/1)' in place['planning_detail'] and place['mtc_stages'] == []
        assert not place['released'] and 'GOAL_STATE_INVALID' in read('stack.log')
        carry = [json.loads(l) for l in read('skills/carry.jsonl').splitlines()]
        assert len([v for v in carry if v['event']=='start']) == 1
        assert not [v for v in carry if v['event']=='stop' and v.get('cause')=='release']
        motions = [json.loads(l) for l in read('skills/move_to_pose.jsonl').splitlines()]
        assert len(motions) == 3 and all(v['outcome']=='SUCCEEDED' for v in motions)
        identity = json.loads(read('identity.stdout'))
        assert identity['source_revision'] == 'c2583aec1e507386f5733285fe5399003709b4d0' and identity['mismatches'] == []
        mapped = json.loads(read('runtime_native_mapping.json'))
        for name in ['libflexcell_physics_trace.so','libflexcell_contact_trace.so','libflexcell_detachable_carry.so','mtc_planner']:
            a=[h for p,h in mapped.items() if Path(p).name==name]
            b=[h for p,h in identity['native_libraries'].items() if Path(p).name==name]
            assert len(a)==len(b)==1 and a==b
    return dict(status='TCP_PLAN_STOP_REMAINS_REJECTED', source_revision=identity['source_revision'],
                tasks=1, pick_attempts=1, place_trajectories=0, intentional_release=False,
                exact_original_planning_scene='NOT_RECORDED', default_admission='NO_GO')


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
