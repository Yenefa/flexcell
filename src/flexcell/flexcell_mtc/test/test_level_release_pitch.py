"""Issue #121: the opt-in level-release path must actually pick a low pitch.

Same frozen attached-point scene as test_attached_point_plan.py, but the
planner is started with level_release_pitch_tolerance_deg set. The planner
service only: no Gazebo, no actuator, no motion goal.
"""
import json
import math
import os
from copy import deepcopy
from pathlib import Path
import signal
import subprocess
import time
import xml.etree.ElementTree as ET

import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped
from moveit_configs_utils import MoveItConfigsBuilder
from moveit_msgs.msg import AllowedCollisionEntry, AttachedCollisionObject, PlanningScene
from moveit_msgs.srv import GetPlanningScene
from shape_msgs.msg import SolidPrimitive

from flexcell_interfaces.srv import PlanManipulation
from flexcell_skills.joint_follow import relative_pose

TOLERANCE_DEG = 2.0


def pose(position, quaternion=(0., 0., 0., 1.)):
    result = PoseStamped()
    result.header.frame_id = 'world'
    result.pose.position.x, result.pose.position.y, result.pose.position.z = map(float, position)
    (result.pose.orientation.x, result.pose.orientation.y,
     result.pose.orientation.z, result.pose.orientation.w) = map(float, quaternion)
    return result


def build(tmp_path, fixture, tolerance_deg):
    description = Path(get_package_share_directory('open_manipulator_description'))
    config = (MoveItConfigsBuilder('open_manipulator_x', package_name='open_manipulator_moveit_config')
              .robot_description(file_path=str(description/'urdf/open_manipulator_x/open_manipulator_x.urdf.xacro'), mappings={'use_sim': 'true'})
              .robot_description_semantic(file_path='config/open_manipulator_x/open_manipulator_x.srdf')
              .joint_limits(file_path='config/open_manipulator_x/joint_limits.yaml')
              .robot_description_kinematics(file_path='config/open_manipulator_x/kinematics.yaml')
              .planning_pipelines(pipelines=['ompl']).to_moveit_configs()).to_dict()
    config['use_sim_time'] = False
    config['level_release_pitch_tolerance_deg'] = float(tolerance_deg)
    params = tmp_path/'params.yaml'
    params.write_text(yaml.safe_dump({'flexcell_mtc_planner': {'ros__parameters': config}}))
    positions = list(fixture['positions'])
    positions[0] = positions[1] = -.011
    from moveit.core.robot_model import RobotModel
    from moveit.core.robot_state import RobotState
    urdf, srdf = tmp_path/'robot.urdf', tmp_path/'robot.srdf'
    urdf.write_text(config['robot_description'])
    srdf.write_text(config['robot_description_semantic'])
    state = RobotState(RobotModel(str(urdf), str(srdf)))
    state.joint_positions = dict(zip(fixture['names'], positions))
    state.update()
    p = state.get_pose('end_effector_link').position
    o = state.get_pose('end_effector_link').orientation
    point_offset, orientation_offset = relative_pose(
        [p.x, p.y, p.z, o.x, o.y, o.z, o.w], fixture['box_pose'])
    scene = PlanningScene()
    scene.robot_model_name = 'open_manipulator_x'
    scene.robot_state.joint_state.name = fixture['names']
    scene.robot_state.joint_state.position = positions
    disabled = [(e.attrib['link1'], e.attrib['link2']) for e in
                ET.fromstring(config['robot_description_semantic']).findall('disable_collisions')]
    names = sorted({n for pair in disabled for n in pair})
    permitted = set(disabled) | {(b, a) for a, b in disabled}
    scene.allowed_collision_matrix.entry_names = names
    scene.allowed_collision_matrix.entry_values = [
        AllowedCollisionEntry(enabled=[(a, b) in permitted for b in names]) for a in names]
    attached = AttachedCollisionObject()
    attached.link_name = 'end_effector_link'
    attached.object.header.frame_id = 'end_effector_link'
    attached.object.id = 'target_box_a'
    attached.object.operation = attached.object.ADD
    attached.object.primitives = [SolidPrimitive(type=SolidPrimitive.BOX, dimensions=[.035, .035, .035])]
    attached.object.primitive_poses = [pose(point_offset, orientation_offset).pose]
    scene.robot_state.attached_collision_objects = [attached]
    request = PlanManipulation.Request()
    request.operation, request.object_name = 'PLACE', 'target_box_a'
    request.object_pose = pose(fixture['box_pose'][:3], fixture['box_pose'][3:])
    request.targets = [pose([.12, -.15, .1675]), pose([.12, -.15, .0675]), pose([.12, -.15, .1675])]
    request.attached_object_targets = True
    request.motion_profile_id, request.deadline_ms = 'demo_slow', 15000
    return config, scene, request


def test_level_release_path_selects_a_low_pitch(tmp_path):
    fixture = json.loads(Path(__file__).with_name('attached_point_fixture.json').read_text())
    config, scene, request = build(tmp_path, fixture, TOLERANCE_DEG)
    environment = dict(os.environ, ROS_DOMAIN_ID='76', ROS_AUTOMATIC_DISCOVERY_RANGE='LOCALHOST')
    os.environ['ROS_DOMAIN_ID'] = '76'
    log = (tmp_path/'planner.log').open('w')
    executable = ([os.environ['FLEXCELL_MTC_TEST_EXECUTABLE']] if 'FLEXCELL_MTC_TEST_EXECUTABLE' in os.environ
                  else ['ros2', 'run', 'flexcell_mtc', 'mtc_planner'])
    process = subprocess.Popen(executable + ['--ros-args', '--params-file', str(tmp_path/'params.yaml')],
                               env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    rclpy.init()
    node = rclpy.create_node('level_release_case')

    def reply(query, response):
        response.scene = scene
        return response

    server = node.create_service(GetPlanningScene, '/get_planning_scene', reply)
    client = node.create_client(PlanManipulation, '/flexcell/mtc/plan')
    try:
        assert client.wait_for_service(timeout_sec=20), (tmp_path/'planner.log').read_text()[-3000:]
        future = client.call_async(deepcopy(request))
        end = time.monotonic() + 40
        while not future.done() and time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=.05)
        assert future.done(), 'planner did not return within bound'
        response = future.result()
        (tmp_path/'response.json').write_text(json.dumps(
            {'success': bool(response.success), 'detail': response.detail}, indent=2))
        assert response.success, response.detail
        assert len(response.trajectories) == 3
        # The adapter reports the pitch it selected; the feature must be active.
        assert 'level-release seed pitch=' in response.detail, response.detail
        reported = response.detail.split('level-release seed pitch=')[1].split(' rad')[0]
        reported_deg = math.degrees(float(reported))
        assert abs(reported_deg) <= TOLERANCE_DEG + .5, reported_deg
        # And the descend endpoint the executor would actually run must agree.
        joints = response.trajectories[1].joint_trajectory
        endpoint = dict(zip(joints.joint_names, joints.points[-1].positions))
        pitch = endpoint['joint2'] + endpoint['joint3'] + endpoint['joint4']
        assert abs(math.degrees(pitch)) <= TOLERANCE_DEG + .5, math.degrees(pitch)
    finally:
        node.destroy_service(server)
        node.destroy_node()
        rclpy.shutdown()
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGINT)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=5)
        log.close()
