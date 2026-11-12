#!/usr/bin/env python3
"""Read native traces; audit actual contact and motion without changing grading."""
import argparse
import bisect
import hashlib
import json
import math
from pathlib import Path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def rotate(q, v):
    x, y, z, w = q
    a, b, c = v
    tx, ty, tz = 2*(y*c-z*b), 2*(z*a-x*c), 2*(x*b-y*a)
    return [a+w*tx+y*tz-z*ty, b+w*ty+z*tx-x*tz, c+w*tz+x*ty-y*tx]


def ee(pose):
    return [a+b for a,b in zip(pose[:3], rotate(pose[3:], [.126, 0., 0.]))]


def pitch(q):
    x,y,z,w = q
    return math.degrees(math.asin(max(-1., min(1., 2*(w*y-z*x)))))


def audit_run(path):
    physics = rows(path/'physics.jsonl')
    contacts = rows(path/'contacts.jsonl')
    motions = rows(path/'sim/skills/move_to_pose.jsonl')
    pushes = rows(path/'sim/skills/push.jsonl')
    by_sim = {r['sim_ns']:r for r in physics}
    stamps = [r['monotonic_ns'] for r in physics]

    def nearest(stamp):
        i = bisect.bisect_left(stamps, stamp)
        return min(range(max(0, i-1), min(len(stamps), i+1)), key=lambda j:abs(stamps[j]-stamp))

    result = []
    for attempt, push in enumerate(pushes):
        direction = push['resolved']['direction'] if 'resolved' in push else push['events'][0]['direction']
        norm = math.hypot(*direction[:2])
        u = [direction[0]/norm, direction[1]/norm, 0.]
        dot = lambda a,b: sum(x*y for x,y in zip(a,b))
        for event in push['events']:
            if event['event'] != 'INCREMENT':
                continue
            matching = [m for m in motions if math.dist(m['target']['position'], event['target'])<1e-8]
            motion = min(matching, key=lambda m:abs(m['wall_ts']-event['wall_ts']))
            offset = event['monotonic_ns']-event['wall_ts']*1e9
            a = nearest(motion['execution_start']*1e9+offset)
            b = nearest(motion['execution_end']*1e9+offset)
            segment = physics[a:b+1]
            assert len(segment)>1 and all(y['sim_ns']-x['sim_ns']==5000000
                                          for x,y in zip(segment, segment[1:]))
            poses = [r['objects']['target_box_a']['pose'] for r in segment]
            ees = [ee(r['parent_pose']) for r in segment]
            target_progress = [dot([p[i]-poses[0][i] for i in range(3)], u) for p in poses]
            ee_progress = [dot([p[i]-ees[0][i] for i in range(3)], u) for p in ees]
            running_max, backslide = 0., 0.
            for value in ee_progress:
                running_max = max(running_max,value)
                backslide = max(backslide,running_max-value)
            pusher_steps = []
            counts = {}
            for r in contacts:
                if not segment[0]['sim_ns']<=r['sim_ns']<=segment[-1]['sim_ns']:
                    continue
                if r['sim_ns'] not in by_sim:
                    raise ValueError('contact lacks same-step native pose')
                pose = by_sim[r['sim_ns']]['objects']['target_box_a']['pose']
                rear, top, vertical = [], [], []
                for c in r['targets']['target_box_a'].get('contacts',{}).get('contact',[]):
                    names = [c[k].get('name','') for k in ('collision1','collision2')]
                    if 'target_box_a::link::col' not in names:
                        continue
                    other = next(n for n in names if n!='target_box_a::link::col')
                    if not other.startswith('open_manipulator_x::'):
                        continue
                    counts[other] = counts.get(other,0)+1
                    points = c.get('position',[])
                    for p in points:
                        delta = [p.get(k,0.)-pose[i] for i,k in enumerate(('x','y','z'))]
                        local = rotate([-pose[3],-pose[4],-pose[5],pose[6]],delta)
                        top.append(local[2]>=.75*.0175)
                        rear.append(dot(delta,u)<=-.5*.0175)
                    for n in c.get('normal',[]):
                        vertical.append(abs(n.get('z',0.))>=max(abs(n.get('x',0.)),abs(n.get('y',0.))))
                if top:
                    pusher_steps.append(dict(sim_ns=r['sim_ns'], top=sum(top)/len(top),
                                             rear=sum(rear)/len(rear),
                                             vertical=sum(vertical)/len(vertical) if vertical else None))
            last_contact = pusher_steps[-1]['sim_ns'] if pusher_steps else None
            final_object = poses[-1]
            after_contact = (dot([final_object[i]-by_sim[last_contact]['objects']['target_box_a']['pose'][i]
                                  for i in range(3)],u) if last_contact else None)
            average = lambda key: (sum(r[key] for r in pusher_steps if r[key] is not None)
                                  /sum(r[key] is not None for r in pusher_steps)) if pusher_steps else None
            result.append(dict(attempt=attempt, request_id=push['request_id'], increment=event['index'],
                primitive_contact_made=push.get('contact_made'), primitive_error_code=push['error_code'],
                requested_m=push.get('requested_distance_m'),
                reported_pre_return_signed_m=push.get('displacement_along_direction_m'),
                native_execution_object_forward_m=target_progress[-1],
                native_execution_ee_forward_m=ee_progress[-1], max_ee_backslide_m=backslide,
                ee_z_min_m=min(p[2] for p in ees), ee_z_max_m=max(p[2] for p in ees),
                tool_pitch_start_deg=pitch(segment[0]['parent_pose'][3:]),
                tool_pitch_end_deg=pitch(segment[-1]['parent_pose'][3:]),
                peak_object_speed_m_s=max(math.dist(x[:3],y[:3])/.005 for x,y in zip(poses,poses[1:])),
                pusher_contact_steps=len(pusher_steps), pusher_colliders=counts,
                mean_step_top_contact_fraction=average('top'),
                mean_step_rear_contact_fraction=average('rear'),
                mean_step_vertical_normal_fraction=average('vertical'),
                forward_after_last_observed_contact_m=after_contact,
                native_samples=len(segment), sim_start_ns=segment[0]['sim_ns'], sim_end_ns=segment[-1]['sim_ns'],
                endpoint_position_error_m=motion.get('position_error_m'),
                orientation_enforced=motion['orientation_enforced']))
    return dict(run=path.name, strokes=result, source_sha256={str(p.relative_to(path)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [path/'physics.jsonl',path/'contacts.jsonl',path/'sim/skills/move_to_pose.jsonl',path/'sim/skills/push.jsonl']})


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path)
    p.add_argument('runs',nargs='+')
    args = p.parse_args()
    print(json.dumps({name:audit_run(args.root/name) for name in args.runs},indent=2,allow_nan=False))
