"""Independent FK replay of the exact successful planner service snapshots."""
import json
import math
from pathlib import Path

import numpy as np
from moveit.core.robot_model import RobotModel
from moveit.core.robot_state import RobotState
from moveit_msgs.msg import PlanningScene
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.convert import message_to_ordereddict
from flexcell_interfaces.srv import PlanManipulation

root=Path('/home/ros/agentic_workcell_ws/artifacts/joint-point-runtime-20261031')
window=json.loads((root/'joint-window/window.json').read_text())
run=Path(window['episodes'][0]['run'])
def xyz(pose): return np.array([pose.position.x,pose.position.y,pose.position.z])
def matrix(pose):
    x,y,z,w=pose.orientation.x,pose.orientation.y,pose.orientation.z,pose.orientation.w
    norm=math.sqrt(x*x+y*y+z*z+w*w)
    assert .999<=norm<=1.001,(x,y,z,w)
    x,y,z,w=x/norm,y/norm,z/norm,w/norm
    value=np.eye(4)
    value[:3,:3]=[[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                  [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                  [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]]
    value[:3,3]=xyz(pose)
    return value
report=[]
for snapshot in sorted((run/'planner').glob('request-*')):
    request=deserialize_message((snapshot/'request.cdr').read_bytes(),PlanManipulation.Request)
    scene=deserialize_message((snapshot/'scene.cdr').read_bytes(),PlanningScene)
    response=deserialize_message((snapshot/'response.cdr').read_bytes(),PlanManipulation.Response)
    for name,message in [('request',request),('scene',scene),('response',response)]:
        (root/(snapshot.name+'-'+name+'.json')).write_text(json.dumps(message_to_ordereddict(message),indent=2)+'\n')
    item=dict(operation=request.operation, success=response.success, detail=response.detail, endpoint_errors_mm=[])
    if response.success:
        assert len(response.trajectories)==len(response.executor_targets)==3
        model=RobotModel(str(snapshot/'robot_description.xml'),str(snapshot/'robot_description_semantic.xml'))
        state=RobotState(model)
        initial=dict(zip(scene.robot_state.joint_state.name,scene.robot_state.joint_state.position))
        state.joint_positions=initial
        state.update()
        point=None
        if request.attached_object_targets:
            bodies=[body for body in scene.robot_state.attached_collision_objects if body.object.id==request.object_name]
            assert len(bodies)==1 and bodies[0].link_name=='end_effector_link'
            body=bodies[0].object
            assert len(body.primitives)==len(body.primitive_poses)==1
            frame=np.eye(4) if body.header.frame_id=='world' else np.asarray(state.get_global_link_transform(body.header.frame_id))
            world_shape=frame @ matrix(body.pose) @ matrix(body.primitive_poses[0])
            point=(np.linalg.inv(np.asarray(state.get_global_link_transform('end_effector_link'))) @ world_shape)[:3,3]
            assert math.dist(world_shape[:3,3],xyz(request.object_pose.pose))<.002
            item['measured_point_offset_in_ee_m']=point.tolist()
        ee_endpoints=[]
        for index,trajectory in enumerate(response.trajectories):
            joints=trajectory.joint_trajectory
            assert set(joints.joint_names)=={'joint1','joint2','joint3','joint4'}
            state.joint_positions=initial | dict(zip(joints.joint_names,joints.points[-1].positions))
            state.update()
            ee=np.asarray(state.get_global_link_transform('end_effector_link'))
            ee_endpoints.append(ee[:3,3])
            assert math.dist(ee[:3,3],xyz(response.executor_targets[index].pose))<1e-9
            if point is not None and index<2:
                actual=ee[:3,:3]@point+ee[:3,3]
                expected=xyz(request.targets[index].pose)
            elif point is not None:
                actual=ee[:3,3]
                expected=ee_endpoints[1]+xyz(request.targets[2].pose)-xyz(request.targets[1].pose)
            else:
                actual=ee[:3,3]
                expected=xyz(request.targets[index].pose)
            error=math.dist(actual,expected)
            assert error<=1.0001e-4,(request.operation,index,error)
            item['endpoint_errors_mm'].append(error*1000)
    report.append(item)
(root/'planner-fk-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
