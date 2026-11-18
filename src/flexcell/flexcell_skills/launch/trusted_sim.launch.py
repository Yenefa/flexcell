"""Server-only simulation from pinned ROBOTIS packages, without patching them."""
import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, EmitEvent, ExecuteProcess, IncludeLaunchDescription
from launch.actions import OpaqueFunction, RegisterEventHandler, SetEnvironmentVariable
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import xacro
import xml.etree.ElementTree as ET
import yaml
from moveit_configs_utils import MoveItConfigsBuilder


def successful_exit(actions, label):
    def on_exit(event, _context):
        if event.returncode == 0:
            return actions
        return [EmitEvent(event=Shutdown(reason=label + ' failed; downstream startup blocked'))]
    return on_exit


def launch_stack(context):
    world = LaunchConfiguration('world').perform(context)
    params = LaunchConfiguration('params_file').perform(context)
    camera = LaunchConfiguration('camera').perform(context) == 'true'
    description = Path(get_package_share_directory('open_manipulator_description'))
    skills = Path(get_package_share_directory('flexcell_skills'))
    model = description / 'urdf/open_manipulator_x/open_manipulator_x.urdf.xacro'
    document = xacro.process_file(str(model), mappings={'use_sim': 'true'})
    robot = document.toprettyxml(indent='  ')
    config = yaml.safe_load(Path(params).read_text())
    if config['carry_server']['ros__parameters']['carry_backend'] == 'detachable_joint':
        urdf = ET.fromstring(robot)
        gazebo = ET.SubElement(urdf, 'gazebo')
        for object_name in config['observe_server']['ros__parameters']['tracked_objects']:
            plugin = ET.SubElement(gazebo, 'plugin', filename='gz-sim-detachable-joint-system',
                                   name='gz::sim::systems::DetachableJoint')
            for key, value in [('parent_link', 'link5'), ('child_model', object_name), ('child_link', 'link')]:
                ET.SubElement(plugin, key).text = value
            for kind in ('attach', 'detach', 'output'):
                ET.SubElement(plugin, kind + '_topic').text = '/flexcell/detachable/%s/%s' % (
                    object_name, 'state' if kind == 'output' else kind)
        robot = ET.tostring(urdf, encoding='unicode')
    if config['carry_server']['ros__parameters']['carry_backend'] == 'contact_grasp':
        # ros2_control owns every joint it declares and rewrites the command each
        # cycle, so a world plugin cannot drive a joint that is still listed
        # there. Hand the two jaw joints to the contact guard, and drop the mimic
        # (DART does not support it, which left the right finger frozen).
        urdf = ET.fromstring(robot)
        for joint in urdf.findall('joint'):
            if joint.get('name') == 'gripper_right_joint':
                for mimic in joint.findall('mimic'):
                    joint.remove(mimic)
        # The description gives each finger a 1 g inertial. A force-servoed jaw
        # on a 1 g body is numerically untameable (measured: the pads left their
        # joint range under a 20 N command), and the real OMX finger is tens of
        # grams. Set a realistic finger mass before handing the jaw to the guard.
        for link in urdf.findall('link'):
            if link.get('name') in ('gripper_left_link', 'gripper_right_link'):
                inertial = link.find('inertial')
                if inertial is not None:
                    mass = inertial.find('mass')
                    if mass is not None:
                        mass.set('value', '0.040')
                    inertia = inertial.find('inertia')
                    if inertia is not None:
                        for key, value in (('ixx', '2.0e-05'), ('iyy', '2.0e-05'),
                                           ('izz', '2.0e-05'), ('ixy', '0'), ('ixz', '0'),
                                           ('iyz', '0')):
                            inertia.set(key, value)
        for block in urdf.findall('ros2_control'):
            for joint in list(block.findall('joint')):
                if joint.get('name', '').startswith('gripper_'):
                    block.remove(joint)
        robot = ET.tostring(urdf, encoding='unicode')
    spawn = Node(package='ros_gz_sim', executable='create', output='screen',
                 arguments=['-string', robot, '-name', 'open_manipulator_x',
                            '-allow_renaming', 'false', '-z', '0.0'])
    broadcaster = Node(package='controller_manager', executable='spawner', output='screen',
                       arguments=['joint_state_broadcaster', '--controller-manager-timeout', '90',
                                  '--switch-timeout', '30'])
    # The contact carry backend drives both jaw joints from its own world plugin.
    # A ros2_control gripper controller would command the same joints, so it is
    # not spawned in that configuration (DART also cannot honour the URDF mimic,
    # which leaves the right finger unactuated under the controller).
    controller_names = ('arm_controller',)
    if config['carry_server']['ros__parameters']['carry_backend'] != 'contact_grasp':
        controller_names = ('arm_controller', 'gripper_controller')
    controllers = [Node(package='controller_manager', executable='spawner', output='screen',
                        arguments=[name, '--controller-manager-timeout', '90', '--switch-timeout', '30'])
                   for name in controller_names]
    bridges = ['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock',
               '/flexcell/physics_trace@std_msgs/msg/String[gz.msgs.StringMsg']
    remaps = []
    if camera:
        bridges += ['/flexcell/camera/rgb@sensor_msgs/msg/Image[gz.msgs.Image',
                    '/flexcell/camera/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo']
        # The gz camera publishes CameraInfo on /flexcell/camera/camera_info
        # while the documented ROS topic stays /flexcell/camera/rgb/camera_info.
        remaps = ['--ros-args', '-r',
                  '/flexcell/camera/camera_info:=/flexcell/camera/rgb/camera_info']
    gazebo_args = ['gz', 'sim', '-s', '-r', '-v', '2']
    if camera:
        gazebo_args += ['--headless-rendering']
    gazebo_args += [world]
    nodes = [
        SetEnvironmentVariable('GZ_SIM_RESOURCE_PATH', str(description.parent) + ':' +
                               os.environ.get('GZ_SIM_RESOURCE_PATH', '')),
        ExecuteProcess(cmd=gazebo_args, output='screen'),
        Node(package='robot_state_publisher', executable='robot_state_publisher',
             parameters=[{'robot_description': robot, 'use_sim_time': True}], output='screen'),
        Node(package='ros_gz_bridge', executable='parameter_bridge', arguments=bridges + remaps,
             parameters=[{'use_sim_time': True}], output='screen'),
        RegisterEventHandler(OnProcessExit(target_action=spawn,
            on_exit=successful_exit([broadcaster], 'robot model spawn'))),
        RegisterEventHandler(OnProcessExit(target_action=broadcaster,
            on_exit=successful_exit(controllers, 'joint state broadcaster activation'))),
        spawn,
        IncludeLaunchDescription(PythonLaunchDescriptionSource(str(
            Path(get_package_share_directory('open_manipulator_moveit_config')) /
            'launch/open_manipulator_x_moveit.launch.py')),
            launch_arguments={'use_sim': 'true', 'start_rviz': 'false'}.items()),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(str(skills / 'launch/move_to_pose.launch.py')),
                                 launch_arguments={'params_file': params}.items()),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(str(skills / 'launch/week1.launch.py')),
                                 launch_arguments={'params_file': params}.items()),
    ]
    if (config['pick_server']['ros__parameters'].get('skill_backend') == 'mtc' or
            config['carry_server']['ros__parameters']['carry_backend'] == 'detachable_joint'):
        moveit_config = (
            MoveItConfigsBuilder('open_manipulator_x', package_name='open_manipulator_moveit_config')
            .robot_description(file_path=str(model), mappings={'use_sim': 'true'})
            .robot_description_semantic(file_path='config/open_manipulator_x/open_manipulator_x.srdf')
            .joint_limits(file_path='config/open_manipulator_x/joint_limits.yaml')
            .robot_description_kinematics(file_path='config/open_manipulator_x/kinematics.yaml')
            .planning_pipelines(pipelines=['ompl'])
            .to_moveit_configs())
        nodes.append(Node(package='flexcell_mtc', executable='mtc_planner', output='screen',
                          parameters=[moveit_config.to_dict(), {
                              'use_sim_time': True,
                              'tracked_objects': config['observe_server']['ros__parameters']['tracked_objects'],
                              # Optional per-profile planner parameters, declared
                              # under an mtc_planner key in the profile params.yaml
                              # (e.g. the issue #121 level_release_pitch_tolerance_deg).
                              # Profiles that do not declare the key are unchanged.
                              **config.get('mtc_planner', {}).get('ros__parameters', {}),
                          }]))
    return nodes


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('world'), DeclareLaunchArgument('params_file'),
        DeclareLaunchArgument('camera', default_value='false'), OpaqueFunction(function=launch_stack)])
