"""Actual planner service + locked robot FK; no actuator or Gazebo process."""
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time
import xml.etree.ElementTree as ET

import numpy as np
import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped
from moveit.core.robot_model import RobotModel
from moveit.core.robot_state import RobotState
from moveit_configs_utils import MoveItConfigsBuilder
from moveit_msgs.msg import AllowedCollisionEntry, AttachedCollisionObject, CollisionObject, PlanningScene
from moveit_msgs.srv import GetPlanningScene
from rosidl_runtime_py.convert import message_to_ordereddict
from rclpy.serialization import deserialize_message
from shape_msgs.msg import SolidPrimitive

from flexcell_interfaces.srv import PlanManipulation
from flexcell_skills.joint_follow import relative_pose


def pose(position, quaternion=(0., 0., 0., 1.)):
    result = PoseStamped()
    result.header.frame_id = 'world'
    result.pose.position.x, result.pose.position.y, result.pose.position.z = map(float, position)
    (result.pose.orientation.x, result.pose.orientation.y,
     result.pose.orientation.z, result.pose.orientation.w) = map(float, quaternion)
    return result


def components(value):
    p, q = value.position, value.orientation
    return [p.x, p.y, p.z, q.x, q.y, q.z, q.w]


def test_attached_point_place_service_has_fk_valid_endpoints(tmp_path):
    fixture = json.loads(Path(__file__).with_name('attached_point_fixture.json').read_text())
    description = Path(get_package_share_directory('open_manipulator_description'))
    config = (MoveItConfigsBuilder('open_manipulator_x', package_name='open_manipulator_moveit_config')
              .robot_description(file_path=str(description/'urdf/open_manipulator_x/open_manipulator_x.urdf.xacro'), mappings={'use_sim':'true'})
              .robot_description_semantic(file_path='config/open_manipulator_x/open_manipulator_x.srdf')
              .joint_limits(file_path='config/open_manipulator_x/joint_limits.yaml')
              .robot_description_kinematics(file_path='config/open_manipulator_x/kinematics.yaml')
              .planning_pipelines(pipelines=['ompl']).to_moveit_configs()).to_dict()
    config['use_sim_time'] = False
    params = tmp_path/'params.yaml'
    params.write_text(yaml.safe_dump({'flexcell_mtc_planner':{'ros__parameters':config}}))
    urdf, srdf = tmp_path/'robot.urdf', tmp_path/'robot.srdf'
    urdf.write_text(config['robot_description'])
    srdf.write_text(config['robot_description_semantic'])
    model = RobotModel(str(urdf), str(srdf))
    state = RobotState(model)
    positions = list(fixture['positions'])
    # Keep raw measurements in the fixture. The finger sample is 1.7e-18 below
    # the URDF bound; use its commanded setpoint/mimic for this reconstructed
    # planner input. All measured arm joints and the point geometry are retained.
    positions[0] = positions[1] = -.011
    state.joint_positions = dict(zip(fixture['names'], positions))
    state.update()
    ee = components(state.get_pose('end_effector_link'))
    point_offset, orientation_offset = relative_pose(ee, fixture['box_pose'])
    scene = PlanningScene()
    scene.robot_model_name = 'open_manipulator_x'
    scene.robot_state.joint_state.name = fixture['names']
    scene.robot_state.joint_state.position = positions
    # A full GetPlanningScene reply includes the SRDF's existing adjacent-link
    # permissions. An empty full-scene matrix would erase them and fail before
    # this regression ever reaches the point-goal sampler.
    disabled = [(e.attrib['link1'],e.attrib['link2']) for e in
                ET.fromstring(config['robot_description_semantic']).findall('disable_collisions')]
    names = sorted({name for pair in disabled for name in pair})
    permitted = set(disabled) | {(b,a) for a,b in disabled}
    scene.allowed_collision_matrix.entry_names = names
    scene.allowed_collision_matrix.entry_values = [
        AllowedCollisionEntry(enabled=[(a,b) in permitted for b in names]) for a in names]
    attached = AttachedCollisionObject()
    attached.link_name = 'end_effector_link'
    attached.object.header.frame_id = 'end_effector_link'
    attached.object.id = 'target_box_a'
    attached.object.operation = attached.object.ADD
    shape = SolidPrimitive(type=SolidPrimitive.BOX, dimensions=[.035,.035,.035])
    attached.object.primitives = [shape]
    attached.object.primitive_poses = [pose(point_offset, orientation_offset).pose]
    scene.robot_state.attached_collision_objects = [attached]
    request = PlanManipulation.Request()
    request.operation, request.object_name = 'PLACE', 'target_box_a'
    request.object_pose = pose(fixture['box_pose'][:3], fixture['box_pose'][3:])
    request.targets = [pose([.12,-.15,.1675]), pose([.12,-.15,.0675]), pose([.12,-.15,.1675])]
    request.attached_object_targets = True
    request.motion_profile_id, request.deadline_ms = 'demo_slow', 15000
    (tmp_path/'scene.json').write_text(json.dumps(message_to_ordereddict(scene),indent=2))
    (tmp_path/'request.json').write_text(json.dumps(message_to_ordereddict(request),indent=2))
    environment = dict(os.environ, ROS_DOMAIN_ID='73', ROS_AUTOMATIC_DISCOVERY_RANGE='LOCALHOST',
                       FLEXCELL_MTC_DIAGNOSTIC_DIR=str(tmp_path/'snapshots'))
    os.environ['ROS_DOMAIN_ID'] = '73'
    log = (tmp_path/'planner.log').open('w')
    executable = ([os.environ['FLEXCELL_MTC_TEST_EXECUTABLE']] if 'FLEXCELL_MTC_TEST_EXECUTABLE' in os.environ
                  else ['ros2','run','flexcell_mtc','mtc_planner'])
    process = subprocess.Popen(executable+['--ros-args','--params-file',str(params)],
                               env=environment,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    rclpy.init()
    node = rclpy.create_node('frozen_scene')
    def reply(query, response):
        assert query.components.components == 1023
        response.scene = scene
        return response
    server = node.create_service(GetPlanningScene, '/get_planning_scene', reply)
    client = node.create_client(PlanManipulation, '/flexcell/mtc/plan')
    try:
        assert client.wait_for_service(timeout_sec=15), (tmp_path/'planner.log').read_text()
        future = client.call_async(request)
        end = time.monotonic()+35
        while not future.done() and time.monotonic()<end:
            rclpy.spin_once(node,timeout_sec=.05)
        assert future.done(), 'planner did not return within bound'
        response = future.result()
        (tmp_path/'response.json').write_text(json.dumps(message_to_ordereddict(response),indent=2))
        assert response.success, response.detail
        assert len(response.trajectories) == len(response.executor_targets) == 3
        ee_endpoints = []
        for index, trajectory in enumerate(response.trajectories):
            joints = trajectory.joint_trajectory
            assert set(joints.joint_names) == {'joint1','joint2','joint3','joint4'}
            positions = dict(zip(joints.joint_names,joints.points[-1].positions))
            state.joint_positions = dict(zip(fixture['names'],scene.robot_state.joint_state.position)) | positions
            state.update()
            actual = components(state.get_pose('end_effector_link'))
            ee_endpoints.append(actual[:3])
            assert math.dist(actual[:3], components(response.executor_targets[index].pose)[:3]) < 1e-9
            if index < 2:
                transform = state.get_global_link_transform('end_effector_link')
                actual_point = np.asarray(transform)[:3,:3] @ point_offset + np.asarray(transform)[:3,3]
                assert math.dist(actual_point,components(request.targets[index].pose)[:3]) <= 1.0001e-4
        assert math.dist(ee_endpoints[2],np.asarray(ee_endpoints[1])+[0.,0.,.1]) <= 1.0001e-4
        snapshots = sorted((tmp_path/'snapshots').glob('request-*'))
        assert len(snapshots) == 1, 'complete planner snapshots were not retained'
        for name, cls, original in [('request',PlanManipulation.Request,request),
                                    ('scene',PlanningScene,scene),('response',PlanManipulation.Response,response)]:
            restored = deserialize_message((snapshots[0]/(name+'.cdr')).read_bytes(),cls)
            assert message_to_ordereddict(restored) == message_to_ordereddict(original)
        blocker = CollisionObject()
        blocker.id, blocker.header.frame_id = 'goal_blocker', 'world'
        blocker.primitives = [SolidPrimitive(type=SolidPrimitive.BOX,dimensions=[.08,.08,.08])]
        blocker.primitive_poses = [request.targets[0].pose]
        blocker.operation = CollisionObject.ADD
        scene.world.collision_objects.append(blocker)
        (tmp_path/'blocked-scene.json').write_text(json.dumps(message_to_ordereddict(scene),indent=2))
        rejected = client.call_async(request)
        end = time.monotonic()+35
        while not rejected.done() and time.monotonic()<end:
            rclpy.spin_once(node,timeout_sec=.05)
        assert rejected.done()
        denied = rejected.result()
        assert not denied.success and not denied.trajectories and not denied.executor_targets
        assert 'hover' in denied.detail
        snapshots = sorted((tmp_path/'snapshots').glob('request-*'))
        assert len(snapshots)==2
        restored = deserialize_message((snapshots[1]/'scene.cdr').read_bytes(),PlanningScene)
        assert message_to_ordereddict(restored) == message_to_ordereddict(scene)
    finally:
        node.destroy_service(server)
        node.destroy_node()
        rclpy.shutdown()
        if process.poll() is None:
            os.killpg(process.pid,signal.SIGINT)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGTERM)
                process.wait(timeout=5)
        log.close()
