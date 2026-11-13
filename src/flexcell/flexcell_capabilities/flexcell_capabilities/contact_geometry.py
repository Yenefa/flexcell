"""Measured-model finger contact geometry and orientation-constrained arm paths.

This isolated adapter supports the pinned planar OpenMANIPULATOR-X chain. It
does not change PushObject or claim that an EE point is a physical contact.
"""
import hashlib
import math
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

import numpy as np


ARM = ('joint1','joint2','joint3','joint4')
FINGERS = ('gripper_left_link','gripper_right_link')


def ry(angle):
    c,s = math.cos(angle),math.sin(angle)
    return np.array([[c,0.,s],[0.,1.,0.],[-s,0.,c]])


def rz(angle):
    c,s = math.cos(angle),math.sin(angle)
    return np.array([[c,-s,0.],[s,c,0.],[0.,0.,1.]])


def transform(xyz=(0.,0.,0.),rotation=None):
    value=np.eye(4);value[:3,3]=xyz
    if rotation is not None:value[:3,:3]=rotation
    return value


def apply(pose,points):
    return np.asarray(points)@pose[:3,:3].T+pose[:3,3]


def clip(poly,axis,bound,greater):
    """Clip an actual triangle polygon, retaining edge intersections as points."""
    if len(poly)==0:return []
    out=[];a=np.asarray(poly[-1]);ain=(a[axis]>=bound if greater else a[axis]<=bound)
    for b in poly:
        b=np.asarray(b);inside=(b[axis]>=bound if greater else b[axis]<=bound)
        if inside!=ain:
            t=(bound-a[axis])/(b[axis]-a[axis]);out.append(a+t*(b-a))
        if inside:out.append(b)
        a,ain=b,inside
    return out


def box_intersects(triangles,center,half):
    low,high=np.asarray(center)-half,np.asarray(center)+half
    tri=np.asarray(triangles)
    candidates=np.flatnonzero(np.all(tri.max(1)>=low,axis=1)&np.all(tri.min(1)<=high,axis=1))
    for i in candidates:
        poly=list(tri[i])
        for axis in range(3):
            poly=clip(poly,axis,low[axis],True);poly=clip(poly,axis,high[axis],False)
            if not poly:break
        if poly:return True
    return False


class ContactGeometry:
    def __init__(self,urdf,mesh_directory):
        self.urdf=Path(urdf);self.mesh_directory=Path(mesh_directory)
        root=ET.parse(urdf).getroot()
        self.joints={j.get('name'):j for j in root.findall('joint')}
        expected={'joint1':([.012,0.,0.],[0.,0.,1.]),
                  'joint2':([0.,0.,.0595],[0.,1.,0.]),
                  'joint3':([.024,0.,.128],[0.,1.,0.]),
                  'joint4':([.124,0.,0.],[0.,1.,0.])}
        self.limits=[]
        for name,(xyz,axis) in expected.items():
            j=self.joints[name];origin=j.find('origin')
            if (not np.allclose(list(map(float,origin.get('xyz').split())),xyz,atol=1e-12)
                    or origin.get('rpy','0 0 0')!='0 0 0'
                    or not np.allclose(list(map(float,j.find('axis').get('xyz').split())),axis)):
                raise ValueError('unsupported arm geometry: '+name)
            limit=j.find('limit');self.limits.append((float(limit.get('lower')),float(limit.get('upper'))))
        if not np.allclose(list(map(float,self.joints['end_effector_joint'].find('origin').get('xyz').split())),[.126,0.,0.]):
            raise ValueError('unsupported fixed end-effector transform')
        self.meshes={};self.vertices={};self.sources={'urdf':hashlib.sha256(self.urdf.read_bytes()).hexdigest()}
        for link in root.findall('link'):
            collisions=link.findall('collision')
            if not collisions:continue
            if len(collisions)!=1:raise ValueError('one collision mesh per link required')
            collision=collisions[0];mesh=collision.find('geometry/mesh')
            if mesh is None:raise ValueError('unsupported collision geometry')
            path=self.mesh_directory/Path(mesh.get('filename')).name;raw=path.read_bytes()
            count=struct.unpack_from('<I',raw,80)[0]
            if len(raw)!=84+50*count:raise ValueError('binary STL required')
            dtype=np.dtype([('normal','<f4',(3,)),('vertices','<f4',(3,3)),('attr','<u2')])
            tri=np.frombuffer(raw,dtype=dtype,offset=84,count=count)['vertices'].astype(float)
            tri*=np.array(list(map(float,mesh.get('scale','1 1 1').split())))
            origin=collision.find('origin')
            if origin is not None:
                if origin.get('rpy','0 0 0')!='0 0 0':raise ValueError('unsupported collision rotation')
                tri+=np.array(list(map(float,origin.get('xyz','0 0 0').split())))
            self.meshes[link.get('name')]=tri
            self.vertices[link.get('name')]=np.unique(tri.reshape(-1,3),axis=0)
            self.sources[path.name]=hashlib.sha256(raw).hexdigest()

    def frames(self,joints,gripper=(0.,0.)):
        q=np.asarray(joints,dtype=float)
        if q.shape!=(4,) or not np.isfinite(q).all():raise ValueError('invalid arm state')
        frames={'link1':np.eye(4)}
        pose=transform([.012,0.,0.],rz(q[0]));frames['link2']=pose
        for name,xyz,angle in [('link3',[0.,0.,.0595],q[1]),('link4',[.024,0.,.128],q[2]),('link5',[.124,0.,0.],q[3])]:
            pose=pose@transform(xyz,ry(angle));frames[name]=pose
        frames['end_effector_link']=pose@transform([.126,0.,0.])
        frames[FINGERS[0]]=pose@transform([.0817,.021+gripper[0],0.])
        frames[FINGERS[1]]=pose@transform([.0817,-.021-gripper[1],0.])
        return frames

    def inverse(self,position,pitch,seed):
        x,y,z=np.asarray(position,dtype=float)-[.012,0.,0.]
        yaw=math.atan2(y,x);rho=math.hypot(x,y)
        wx=rho-.126*math.cos(pitch);wz=z-.0595+.126*math.sin(pitch)
        a,b=math.hypot(.024,.128),.124;alpha=math.atan2(.128,.024)
        c=(wx*wx+wz*wz-a*a-b*b)/(2*a*b)
        if not -1.<=c<=1.:raise ValueError('fixed-pitch target unreachable')
        options=[]
        for delta in [math.acos(c),-math.acos(c)]:
            shoulder=math.atan2(wz,wx)-math.atan2(b*math.sin(delta),a+b*math.cos(delta))
            q2=alpha-shoulder;q3=-delta-alpha;q4=pitch-q2-q3
            q=np.array([yaw,q2,q3,q4])
            if all(low-1e-10<=v<=high+1e-10 for v,(low,high) in zip(q,self.limits)):
                if np.linalg.norm(self.frames(q)['end_effector_link'][:3,3]-position)>1e-8:
                    raise ValueError('analytical FK/IK disagreement')
                options.append(q)
        if not options:raise ValueError('fixed-pitch target violates joint limits')
        return min(options,key=lambda q:np.linalg.norm(q-np.asarray(seed)))

    def tool_local(self,gripper=(0.,0.)):
        frames=self.frames([0.,0.,0.,0.],gripper);inv=np.linalg.inv(frames['end_effector_link'])
        return {name:apply(inv@frames[name],self.meshes[name]) for name in ['link5',*FINGERS]}

    def tcp_inverse(self,point,pitch,tcp,seed):
        point=np.asarray(point);tcp=np.asarray(tcp)
        x,y=point[:2]-[.012,0.];rho=math.hypot(x,y)
        if abs(tcp[1])>=rho:raise ValueError('lateral TCP offset unreachable')
        yaw=math.atan2(y,x)-math.asin(tcp[1]/rho)
        position=point-(rz(yaw)@ry(pitch)@tcp)
        return self.inverse(position,pitch,seed)

    def world_meshes(self,joints,gripper=(0.,0.),tool_only=False):
        frames=self.frames(joints,gripper)
        names=['link5',*FINGERS] if tool_only else [n for n in self.meshes if n!='link1']
        return {n:apply(frames[n],self.meshes[n]) for n in names}

    def rear_support(self,joints,center,half=.0175,gripper=(0.,0.)):
        """Actual triangle/edge point first touching the box's +x rear plane."""
        best=None;center=np.asarray(center)
        frames=self.frames(joints,gripper)
        for name in ['link5',*FINGERS]:
            vertices=apply(frames[name],self.vertices[name])
            if any(vertices[:,axis].max()<center[axis]-half or vertices[:,axis].min()>center[axis]+half for axis in (1,2)):
                continue
            tri=apply(frames[name],self.meshes[name])
            mask=(tri[:,:,1].max(1)>=center[1]-half)&(tri[:,:,1].min(1)<=center[1]+half)&(tri[:,:,2].max(1)>=center[2]-half)&(tri[:,:,2].min(1)<=center[2]+half)
            for i in np.flatnonzero(mask):
                poly=list(tri[i])
                for axis in (1,2):
                    poly=clip(poly,axis,center[axis]-half,True);poly=clip(poly,axis,center[axis]+half,False)
                    if not poly:break
                if not poly:continue
                point=min(poly,key=lambda p:p[0])
                normal=np.cross(tri[i,1]-tri[i,0],tri[i,2]-tri[i,0]);norm=np.linalg.norm(normal)
                if norm<=1e-16:continue
                if (best is None or point[0]<best['point'][0]-1e-10
                        or abs(point[0]-best['point'][0])<=1e-10 and normal[0]/norm<best['normal'][0]):
                    best=dict(link=name,triangle_index=int(i),point=point.tolist(),
                              normal=(normal/norm).tolist(),triangle_world=tri[i].tolist())
        return best

    def register_finger(self,center,protected,gripper=(0.,0.),pitch=math.radians(85.)):
        """Register actual rear-support triangle, never a bounding-box corner."""
        local=self.tool_local(gripper);tri=local[FINGERS[0]]
        cross=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);area=np.linalg.norm(cross,axis=1)/2
        normal=cross/np.maximum(2*area[:,None],1e-16);centroid=tri.mean(1)
        rotated=normal@ry(pitch).T
        valid=(area>1e-7)&(centroid[:,0]>0.)&(normal[:,2]<-.9)&(rotated[:,0]<-.95)
        indices=np.flatnonzero(valid)
        if not len(indices):raise ValueError('no actual distal finger face meets normal condition')
        i=max(indices,key=lambda j:area[j]);anchor=centroid[i]
        bottom=min(float((v@ry(pitch).T)[:,:,2].min()) for v in local.values())
        ee_z=max(float(center[2]-(ry(pitch)@anchor)[2]),.002-bottom)
        point=np.array([center[0]+.0175+.0015,center[1],ee_z+(ry(pitch)@anchor)[2]])
        q=np.zeros(4)
        for _ in range(10):
            q=self.tcp_inverse(point,pitch,anchor,q);support=self.rear_support(q,center,gripper=gripper)
            if support is None:raise ValueError('no finger surface overlaps object height/width')
            error=center[0]+.0175+.0015-support['point'][0]
            point[0]+=error
            if abs(error)<1e-6:break
        q=self.tcp_inverse(point,pitch,anchor,q);support=self.rear_support(q,center,gripper=gripper)
        if (support['link']!=FINGERS[0] or support['normal'][0]>-.95
                or abs(support['point'][0]-(center[0]+.0175+.0015))>1e-5):
            raise ValueError('other geometry intercepts the proposed contact')
        clearance=self.guards(q,protected,gripper)
        frame=self.frames(q,gripper)['end_effector_link']
        tcp=frame[:3,:3].T@(np.asarray(support['point'])-frame[:3,3])
        index=support['triangle_index']
        face=local[FINGERS[0]][index]
        face_normal=np.cross(face[1]-face[0],face[2]-face[0]);face_normal/=np.linalg.norm(face_normal)
        c=np.cross(local[FINGERS[0]][:,1]-local[FINGERS[0]][:,0],local[FINGERS[0]][:,2]-local[FINGERS[0]][:,0])
        c/=np.maximum(np.linalg.norm(c,axis=1)[:,None],1e-16)
        patch=np.flatnonzero((c@face_normal>.9999)&(np.abs((local[FINGERS[0]][:,0]-face[0])@face_normal)<1e-5))
        return dict(schema_version=1,frame='end_effector_link',finger=FINGERS[0],
                    tcp=tcp.tolist(),triangle_index=index,triangle_in_ee=local[FINGERS[0]][index].tolist(),
                    patch_triangle_indices=patch.tolist(),patch_in_ee=local[FINGERS[0]][patch].tolist(),
                    support_world=support,approach_joints=q.tolist(),pitch_rad=pitch,
                    gripper_positions=list(gripper),minimum_floor_clearance_m=clearance,
                    source_sha256=self.sources)

    def guards(self,joints,protected,gripper=(0.,0.),floor=.001):
        frames=self.frames(joints,gripper);minimum=float('inf')
        for name,vertices in self.vertices.items():
            if name=='link1':continue
            vertices=apply(frames[name],vertices);minimum=min(minimum,float(vertices[:,2].min()))
            for center in protected:
                low,high=np.asarray(center)-(.0175+.002),np.asarray(center)+(.0175+.002)
                if np.all(vertices.max(0)>=low) and np.all(vertices.min(0)<=high):
                    if box_intersects(apply(frames[name],self.meshes[name]),center,.0175+.002):
                        raise ValueError('planned mesh intersects protected object: '+name)
        if minimum<floor:raise ValueError('planned mesh crosses table clearance: %.6f'%minimum)
        return minimum

    def cartesian(self,start,tcp,end_point,end_pitch,protected,gripper=(0.,0.),duration=None,
                  avoid_target=None,abort_check=None):
        """Smooth dense TCP path; every sample has explicit orientation and IK."""
        start=np.asarray(start);frame=self.frames(start,gripper)['end_effector_link']
        initial=apply(frame,np.asarray(tcp));initial_pitch=float(sum(start[1:]))
        end_point=np.asarray(end_point);steps=max(40,int(np.linalg.norm(end_point-initial)/.0005),int(abs(end_pitch-initial_pitch)/.005))
        u=np.linspace(0.,1.,steps+1);s=10*u**3-15*u**4+6*u**5
        path=[];tcp_points=[];q=start
        for fraction in s:
            if abort_check is not None and abort_check():raise InterruptedError('caller canceled during read-only geometry')
            p=initial+(end_point-initial)*fraction;pitch=initial_pitch+(end_pitch-initial_pitch)*fraction
            for _ in range(8):
                q=self.tcp_inverse(p,pitch,tcp,q)
                if avoid_target is None:break
                support=self.rear_support(q,avoid_target,gripper=gripper)
                if support is None:break
                short=avoid_target[0]+.0175+.0015-support['point'][0]
                if short<=1e-6:break
                p=p+np.array([short,0.,0.])
            q=self.tcp_inverse(p,pitch,tcp,q)
            if avoid_target is not None:
                support=self.rear_support(q,avoid_target,gripper=gripper)
                if support is not None and support['point'][0]<avoid_target[0]+.0175+.0014:
                    raise ValueError('approach mesh crosses the target rear corridor')
            path.append(q);tcp_points.append(p)
        path=np.array(path);d1=np.gradient(path,u,axis=0);d2=np.gradient(d1,u,axis=0)
        d1[[0,-1]]=0.;d2[[0,-1]]=0.
        # demo_veryslow: URDF 4.8 rad/s * .05; MoveIt 5 rad/s² * .05.
        minimum=max(.4,float(np.abs(d1).max()/.24),math.sqrt(float(np.abs(d2).max()/.25)))
        duration=max(minimum*1.15,duration or 0.)
        if duration>20.:raise ValueError('trajectory exceeds isolated segment time budget')
        for q in path:
            if abort_check is not None and abort_check():raise InterruptedError('caller canceled during read-only geometry')
            self.guards(q,protected,gripper)
            if avoid_target is not None:
                for name,tri in self.world_meshes(q,gripper).items():
                    if box_intersects(tri,avoid_target,.0175):
                        raise ValueError('approach mesh intersects the target: '+name)
        # Screen cubic midpoint proxies as well as knots. This is not a proof
        # for every controller spline; validate actual execution in native data.
        for i in range(len(path)-1):
            if abort_check is not None and abort_check():raise InterruptedError('caller canceled during read-only geometry')
            midpoint=(path[i]+path[i+1])/2+(d1[i]-d1[i+1])*(u[i+1]-u[i])/8
            self.guards(midpoint,protected,gripper)
            actual=apply(self.frames(midpoint,gripper)['end_effector_link'],tcp)
            expected=(np.asarray(tcp_points[i])+tcp_points[i+1])/2
            if np.linalg.norm(actual-expected)>.0005:
                raise ValueError('interpolated joint path leaves the TCP corridor')
        return dict(positions=path,times=u*duration,velocities=d1/duration,accelerations=d2/duration**2,
                    tcp_points=np.asarray(tcp_points),tcp_start=initial.tolist(),tcp_end=tcp_points[-1].tolist(),
                    pitch_start=initial_pitch,pitch_end=end_pitch)
