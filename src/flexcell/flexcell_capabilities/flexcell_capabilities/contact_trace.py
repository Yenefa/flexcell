"""Read-only native-contact monitor. Absent telemetry remains unknown."""
from collections import deque
import json
import math
from pathlib import Path
import time

import numpy as np
from flexcell_capabilities.contact_geometry import ARM


def fresh_joint_values(samples,physical_sim_ns,now_s):
    """Newest complete measured joints at/before a coherent native frame.

    ROS /clock delivery can lag JointState delivery. A future sample relative
    to the physical reference is retained for a later frame, never extrapolated
    or silently clamped to age zero. Both original250ms age bounds remain.
    """
    if type(physical_sim_ns) is not int:return None
    needed=[*ARM,'gripper_left_joint','gripper_right_joint']
    for msg,received in reversed(samples):
        stamp=msg.header.stamp.sec*10**9+msg.header.stamp.nanosec
        source_age=(physical_sim_ns-stamp)/1e9;wall_age=now_s-received
        if not 0<=source_age<=.25 or not 0<=wall_age<=.25:continue
        names=list(msg.name)
        if len(names)!=len(set(names)) or len(names)!=len(msg.position):continue
        values=dict(zip(names,msg.position))
        if not all(n in values and math.isfinite(values[n]) for n in needed):continue
        return (np.array([values[n] for n in ARM]),tuple(values[n] for n in needed[-2:]),
                dict(joint_source_stamp_ns=stamp,native_source_stamp_ns=physical_sim_ns,
                     source_age_s=source_age,wall_age_s=wall_age))
    return None


def rotation(quaternion):
    x,y,z,w=quaternion
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                     [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                     [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])


def patch_distance(point,triangles):
    tri=np.asarray(triangles,dtype=float)
    if len(tri)==0:return float('inf')
    p=np.asarray(point);a,b,c=tri[:,0],tri[:,1],tri[:,2];ab,ac=b-a,c-a
    n=np.cross(ab,ac);length=np.linalg.norm(n,axis=1);valid=length>1e-16
    n=n/np.maximum(length[:,None],1e-16);signed=np.einsum('ij,ij->i',p-a,n)
    projection=p-n*signed[:,None];v=projection-a
    aa=np.einsum('ij,ij->i',ab,ab);bb=np.einsum('ij,ij->i',ac,ac);cc=np.einsum('ij,ij->i',ab,ac)
    av=np.einsum('ij,ij->i',v,ab);cv=np.einsum('ij,ij->i',v,ac)
    denominator=aa*bb-cc*cc;safe=np.maximum(denominator,1e-30)
    u=(bb*av-cc*cv)/safe;w=(aa*cv-cc*av)/safe
    inside=valid&(denominator>1e-20)&(u>=-1e-8)&(w>=-1e-8)&(u+w<=1+1e-8)
    best=float(np.abs(signed[inside]).min()) if inside.any() else float('inf')
    for x,y in [(a,b),(b,c),(c,a)]:
        edge=y-x;t=np.einsum('ij,ij->i',p-x,edge)/np.maximum(np.einsum('ij,ij->i',edge,edge),1e-20)
        near=x+np.clip(t,0,1)[:,None]*edge
        best=min(best,float(np.linalg.norm(p-near,axis=1).min()))
    return best


class JsonTail:
    def __init__(self,path):self.path=Path(path);self.offset=0;self.pending=''
    def read(self):
        if not self.path.exists():return []
        with self.path.open() as stream:
            stream.seek(self.offset);data=stream.read();self.offset=stream.tell()
        lines=(self.pending+data).split('\n');self.pending=lines.pop()
        return [json.loads(line) for line in lines if line]


class NativeContact:
    def __init__(self,directory,target,protected):
        self.physics=JsonTail(Path(directory)/'physics.jsonl');self.contacts=JsonTail(Path(directory)/'contacts.jsonl')
        self.target,self.protected=target,protected;self.frames={};self.order=deque();self.pending=[]
        self.latest=None;self.latest_physics=None;self.matched_physics=None;self.error=None;self.protected_peak=0.
        self.registry=None;self.active=False;self.start_ns=0;self.steps=0;self.points=[]
        self.bad=None;self.other=set();self.max_patch_error=0.
        self.sim_clock=None
        self.first_physics_ns=None;self.pre_robot_contact_prefix_records=0

    def begin(self,registry):
        self.registry=registry;self.active=True;self.start_ns=time.monotonic_ns()
        self.steps=0;self.points=[];self.bad=None;self.other=set();self.max_patch_error=0.

    def end(self):self.active=False

    def poll(self):
        try:
            for row in self.physics.read():
                if self.first_physics_ns is None:self.first_physics_ns=row['sim_ns']
                self.latest_physics=row;ns=row['sim_ns'];self.frames[ns]=row;self.order.append(ns)
                while len(self.order)>4096:self.frames.pop(self.order.popleft(),None)
            self.pending.extend(self.contacts.read());pending=[]
            for row in self.pending:
                for name,origin in self.protected.items():
                    pose=row['targets'].get(name,{}).get('pose')
                    if pose is None:self.error='protected native pose missing'
                    else:self.protected_peak=max(self.protected_peak,math.dist(pose[:3],origin))
                # A sequential tail can read contacts one or two steps ahead of
                # physics. Freshness and contact geometry must use the SAME
                # native simulation step, including while the monitor is idle.
                if row['sim_ns'] not in self.frames:
                    if self.first_physics_ns is not None and row['sim_ns']<self.first_physics_ns:
                        # ContactTrace runs before the robot link exists; these
                        # bootstrap rows cannot contain an arm pose. Retain raw
                        # rows and report their count, without calling them
                        # observed contact. Never skip a later missing step.
                        self.pre_robot_contact_prefix_records+=1
                    elif self.order and row['sim_ns']<self.order[0]:
                        self.error='native contact step expired without a physics match'
                    else:pending.append(row)
                    continue
                native=self.frames[row['sim_ns']]
                if self.latest is None or row['sim_ns']>=self.latest['sim_ns']:
                    self.latest=row;self.matched_physics=native
                if not self.active or row['monotonic_ns']<self.start_ns:continue
                entry=row['targets'][self.target]
                if not entry['component_present'] or entry['contacts'] is None:
                    self.bad='native contact component unavailable';continue
                parent=native['parent_pose'];R=rotation(parent[3:])
                ee=np.asarray(parent[:3])+R@np.array([.126,0.,0.])
                found=False
                for contact in entry['contacts'].get('contact',[]):
                    names=[contact[k].get('name','') for k in ('collision1','collision2')]
                    if self.target+'::link::col' not in names:continue
                    other=next(n for n in names if n!=self.target+'::link::col')
                    if not other.startswith('open_manipulator_x::'):continue
                    if other!='open_manipulator_x::'+self.registry['finger']+'::'+self.registry['finger']+'_collision':
                        self.other.add(other)
                    found=True
                    points=contact.get('position',[]);normals=contact.get('normal',[])
                    for index,point in enumerate(points):
                        p=np.array([point.get(k,0.) for k in ('x','y','z')]);local=R.T@(p-ee)
                        error=patch_distance(local,self.registry['patch_in_ee'])
                        self.max_patch_error=max(self.max_patch_error,error)
                        normal=normals[min(index,len(normals)-1)] if normals else {}
                        n=np.array([normal.get(k,0.) for k in ('x','y','z')]);length=np.linalg.norm(n)
                        xdom=abs(n[0])/length if length else 0.
                        rear=(p[0]-entry['pose'][0])>=.5*.0175
                        self.points.append((bool(rear),float(xdom),float(error)))
                self.steps+=int(found)
            self.pending=pending
        except Exception as exc:self.error='native telemetry invalid: '+str(exc)

    def fresh(self):
        if (self.error is not None or self.latest is None
                or self.latest_physics is None or self.matched_physics is None):return False
        now=time.monotonic_ns()
        ages=[(now-row['monotonic_ns'])/1e9 for row in (self.latest,self.matched_physics)]
        if not self.latest['targets'][self.target]['component_present'] or min(ages)<0:return False
        if (self.latest['sim_ns']!=self.matched_physics['sim_ns']
                or not 0<=self.latest_physics['sim_ns']-self.latest['sim_ns']<=15_000_000):return False
        if max(ages)<=.25:return True
        # Gazebo may stop advancing physics and /clock while the host is
        # descheduled. A wall gap is not a missing physical step in that case.
        # Require coherent native streams and /clock no more than three 5ms
        # steps AHEAD of them, with a separate bounded 2s wall watchdog. ROS
        # /clock is a transported consumer clock and may lag native ECM time;
        # that lag cannot make a coherent producer frame "from the future".
        # If /clock advances beyond native telemetry the exception never applies.
        if self.sim_clock is None or max(ages)>2.:return False
        sim_now=self.sim_clock()
        return sim_now-self.latest['sim_ns']<=15_000_000

    def freshness_info(self):
        now=time.monotonic_ns();sim_now=self.sim_clock() if self.sim_clock else None
        return {name:None if row is None else dict(
                    wall_age_s=(now-row['monotonic_ns'])/1e9,source_sim_ns=row['sim_ns'],
                    clock_minus_source_ns=None if sim_now is None else sim_now-row['sim_ns'])
                for name,row in [('physics',self.matched_physics),('contacts',self.latest),
                                 ('raw_physics',self.latest_physics)]}

    def observed(self):
        if not self.fresh() or self.bad:return None
        return self.steps>0

    def summary(self):
        return dict(physical_contact_observed=self.observed(),contact_steps=self.steps,
                    rear_fraction=sum(p[0] for p in self.points)/len(self.points) if self.points else None,
                    horizontal_normal_fraction=sum(p[1]>=.8 for p in self.points)/len(self.points) if self.points else None,
                    maximum_patch_distance_m=self.max_patch_error,unexpected_robot_colliders=sorted(self.other),
                    source_problem=self.bad or self.error,protected_peak_m=self.protected_peak,
                    freshness=self.freshness_info(),
                    pre_robot_contact_prefix_records=self.pre_robot_contact_prefix_records)

    def guard(self):
        if not self.fresh():return self.error or 'native contact source stale/unavailable'
        if self.bad:return self.bad
        if self.protected_peak>.005:return 'protected object moved'
        if self.other:return 'unexpected robot surface contacts target'
        if self.steps>=5 and self.points:
            s=self.summary()
            if s['rear_fraction']<.7 or s['horizontal_normal_fraction']<.7:return 'observed contact is not the registered rear-side contact'
            if self.max_patch_error>.002:return 'observed contact lies off the actual registered mesh patch'
        return None
