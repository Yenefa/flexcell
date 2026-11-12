"""Read-only replay of native trajectories and emitted returned-state receipts.

This does not replace the frozen task evaluator. Native world poses, rather than
ROS /tf link transforms, establish physical TCP motion.
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'src/flexcell/flexcell_skills'))
from flexcell_skills.contact_receipt import ready_for_next
from flexcell_skills.contact_trace import rotation,patch_distance
from flexcell_skills.contact_geometry import ContactGeometry


def rows(path):
    with path.open() as stream:
        for line in stream:
            yield json.loads(line)


def analyze(directory):
    trial=directory/'trial'
    events=list(rows(trial/'events.jsonl'))
    phases=[];active=None;attempt=-1
    for event in events:
        if event['kind']=='DECISION' and event['decision']=='push':attempt+=1
        if event['kind']=='CONSTRAINED_DISPATCH':
            active=dict(event,attempt=attempt,points_native=[])
            phases.append(active)
        if event['kind'] in ('CONSTRAINED_TERMINAL','MOTION_TERMINAL_UNKNOWN') and active is not None:
            active['terminal']=event;active=None
    registers={int(p.stem.rsplit('_',1)[1]):json.loads(p.read_text())
               for p in trial.glob('contact_frame_*.json')}
    model=ContactGeometry(directory.parent/'model/robot.urdf',directory.parent/'model')
    registered_gripper=registers[min(registers)]['gripper_positions'] if registers else (0.,0.)
    tool_vertices=np.unique(np.concatenate([t.reshape(-1,3) for t in model.tool_local(registered_gripper).values()]),axis=0)
    target_positions=[];native_count=0;native_frames={};bad_intervals=0;last_sim=None;tool_floor_min=float('inf')
    last_wall=None;maximum_wall_gap_ns=0;maximum_phase_gap_ns=0
    for row in rows(directory/'physics.jsonl'):
        native_count+=1;target_positions.append(row['objects']['target_box_a']['pose'][:3])
        native_frames[row['sim_ns']]=row['parent_pose']
        if last_sim is not None and row['sim_ns']-last_sim!=5_000_000:bad_intervals+=1
        last_sim=row['sim_ns']
        if last_wall is not None:
            maximum_wall_gap_ns=max(maximum_wall_gap_ns,row['monotonic_ns']-last_wall)
            for phase in phases:
                overlap=max(0,min(row['monotonic_ns'],phase.get('terminal',{}).get('monotonic_ns',0))-
                              max(last_wall,phase['monotonic_ns']))
                maximum_phase_gap_ns=max(maximum_phase_gap_ns,overlap)
        last_wall=row['monotonic_ns']
        parent=row['parent_pose'];R=rotation(parent[3:]);ee=np.asarray(parent[:3])+R@[.126,0.,0.]
        tool_floor_min=min(tool_floor_min,float(ee[2]+np.min(tool_vertices@R[2])))
        for phase in phases:
            terminal=phase.get('terminal',{})
            if phase['monotonic_ns']<=row['monotonic_ns']<=terminal.get('monotonic_ns',0):
                tcp=np.asarray(registers[phase['attempt']]['tcp'])+[.126,0.,0.]
                actual=np.asarray(parent[:3])+R@tcp
                pitch=float(np.arctan2(-R[2,0],np.hypot(R[0,0],R[1,0])))
                phase['points_native'].append([*actual,pitch])
    result=[]
    for phase in phases:
        points=np.asarray(phase.pop('points_native'))
        entry={k:phase[k] for k in ('phase','attempt','request_id','duration_s','tcp_start','tcp_end','pitch_start','pitch_end')}
        entry['terminal']=phase.get('terminal');entry['native_samples']=len(points)
        if len(points):
            entry['tcp_actual_start_m']=points[0,:3].tolist()
            entry['tcp_actual_end_m']=points[-1,:3].tolist()
            entry['endpoint_error_m']=float(np.linalg.norm(points[-1,:3]-phase['tcp_end']))
            if phase['phase']=='STROKE':
                origin=np.asarray(phase['tcp_start'])
                delta=points[:,:3]-origin
                entry.update(forward_travel_m=float(-delta[-1,0]),
                    maximum_lateral_vertical_error_m=float(np.linalg.norm(delta[:,1:],axis=1).max()),
                    maximum_pitch_error_rad=float(np.abs(points[:,3]-phase['pitch_end']).max()))
        result.append(entry)
    # Recompute contact evidence from raw ECM records, independently of the
    # controller's running summary. Join only matching native simulation steps.
    windows={};attempt=-1
    for event in events:
        kind=event['kind']
        if kind=='DECISION' and event['decision']=='push':attempt+=1
        if kind=='CONSTRAINED_DISPATCH' and event['phase']=='STROKE':
            windows.setdefault(attempt,dict(start=event['monotonic_ns'],end=None))
        if kind in ('STROKE_VERDICT','POST_RETURN_RECEIPT') and attempt in windows:
            if windows[attempt]['end'] is None:windows[attempt]['end']=event['monotonic_ns']
    contacts={i:dict(native_contact_steps=0,points=0,rear_points=0,horizontal_points=0,
        maximum_patch_distance_m=0.,unexpected_robot_colliders=set(),unjoined_steps=0)
        for i in windows}
    for window in windows.values():
        if window['end'] is None:
            window['end']=events[-1]['monotonic_ns'];window['incomplete']=True
    for row in rows(directory/'contacts.jsonl'):
        for index,window in windows.items():
            if not window['start']<=row['monotonic_ns']<=window['end']:continue
            entry=row['targets']['target_box_a'];stats=contacts[index];found=False
            parent=native_frames.get(row['sim_ns'])
            if parent is None:stats['unjoined_steps']+=1;continue
            R=rotation(parent[3:]);ee=np.asarray(parent[:3])+R@[.126,0.,0.]
            expected='open_manipulator_x::'+registers[index]['finger']+'::'+registers[index]['finger']+'_collision'
            for contact in (entry.get('contacts') or {}).get('contact',[]):
                names=[contact[k].get('name','') for k in ('collision1','collision2')]
                robot=[n for n in names if n.startswith('open_manipulator_x::')]
                if not robot:continue
                found=True
                for name in robot:
                    if name!=expected:stats['unexpected_robot_colliders'].add(name)
                normals=contact.get('normal',[])
                for p_index,p in enumerate(contact.get('position',[])):
                    point=np.array([p.get(k,0.) for k in ('x','y','z')])
                    error=patch_distance(R.T@(point-ee),registers[index]['patch_in_ee'])
                    stats['maximum_patch_distance_m']=max(stats['maximum_patch_distance_m'],error)
                    n=normals[min(p_index,len(normals)-1)] if normals else {}
                    normal=np.array([n.get(k,0.) for k in ('x','y','z')]);length=np.linalg.norm(normal)
                    stats['points']+=1
                    stats['rear_points']+=int(point[0]-entry['pose'][0]>=.5*.0175)
                    stats['horizontal_points']+=int(length>0 and abs(normal[0])/length>=.8)
            stats['native_contact_steps']+=int(found)
    for stats in contacts.values():
        stats['unexpected_robot_colliders']=sorted(stats['unexpected_robot_colliders'])
        stats['rear_fraction']=stats['rear_points']/stats['points'] if stats['points'] else None
        stats['horizontal_normal_fraction']=stats['horizontal_points']/stats['points'] if stats['points'] else None
    receipts=[]
    for event in events:
        if event['kind']!='POST_RETURN_RECEIPT':continue
        value=event['receipt'];post=value.get('post_return')
        entry=dict(receipt=value)
        if post:
            entry['ready_at_emission_replayed']=ready_for_next(value,event['sim_ns'],post['revision'],event['monotonic_ns'])
            entry['expired_300ms_later']=not ready_for_next(value,event['sim_ns'],post['revision'],event['monotonic_ns']+300_000_000)
        receipts.append(entry)
    positions=np.asarray(target_positions)
    return dict(native_physics_samples=native_count,non_5ms_intervals=bad_intervals,
        maximum_native_wall_gap_s_including_startup=maximum_wall_gap_ns/1e9,
        maximum_no_native_update_within_dispatched_phase_s=maximum_phase_gap_ns/1e9,
        minimum_native_tool_floor_clearance_m=tool_floor_min if native_count else None,
        native_tool_gripper_assumption='registered positions; compare unchanged frozen gripper gate and raw joints',
        net_signed_m=float(positions[0,0]-positions[-1,0]) if len(positions) else None,
        maximum_object_center_z_m=float(positions[:,2].max()) if len(positions) else None,
        constrained_phases=result,receipts=receipts,independent_native_contact=contacts,
        summary=json.loads((trial/'contact_summary.json').read_text()),
        independent_verdict=json.loads((directory/'verdict.json').read_text()))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    data=analyze(args.directory)
    with args.out.open('x') as stream:json.dump(data,stream,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in data.items() if k not in ('constrained_phases','receipts')},indent=2))
