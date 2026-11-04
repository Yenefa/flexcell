"""Run the upstream detector and fixed sensor TF; no actuator or task nodes."""
import json
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from flexcell_skills.vision_geometry import optical_pose, validate_calibration


def setup(context):
    calibration = json.loads(Path(LaunchConfiguration('calibration').perform(context)).read_text())
    validate_calibration(calibration)
    pose = optical_pose(calibration['camera_sdf_pose'])
    args = []
    for key, value in zip(('x', 'y', 'z', 'qx', 'qy', 'qz', 'qw'), pose):
        args += ['--' + key, str(value)]
    args += ['--frame-id', 'world', '--child-frame-id', calibration['camera_frame']]
    config = Path(get_package_share_directory('flexcell_skills')) / 'config' / 'apriltag.yaml'
    nodes = [
        Node(package='tf2_ros', executable='static_transform_publisher', arguments=args,
             parameters=[{'use_sim_time': True}], output='screen'),
        Node(package='apriltag_ros', executable='apriltag_node', name='apriltag',
             namespace='flexcell_vision', parameters=[str(config), {
                 'use_sim_time': True,
                 'size': calibration['tag_size_m'],
                 'tag.ids': [tag['id'] for tag in calibration['tags']],
                 'tag.frames': [tag['frame'] for tag in calibration['tags']],
                 'tag.sizes': [calibration['tag_size_m']] * len(calibration['tags']),
             }],
             remappings=[('image_rect', '/flexcell/camera/rgb'),
                         ('camera_info', '/flexcell/camera/rgb/camera_info'),
                         ('/flexcell/camera/camera_info', '/flexcell/camera/rgb/camera_info')],
             output='screen'),
    ]
    world = LaunchConfiguration('world').perform(context)
    if world:
        if calibration.get('perception_only') is not True:
            raise ValueError('standalone world requires a perception_only profile')
        nodes[:0] = [
            ExecuteProcess(cmd=['gz', 'sim', '-s', '-r', '--headless-rendering', world],
                           output='screen'),
            Node(package='ros_gz_bridge', executable='parameter_bridge',
                 arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock',
                            '/flexcell/camera/rgb@sensor_msgs/msg/Image[gz.msgs.Image',
                            '/flexcell/camera/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo'],
                 remappings=[('/flexcell/camera/camera_info', '/flexcell/camera/rgb/camera_info')],
                 parameters=[{'use_sim_time': True}], output='screen'),
        ]
    return nodes


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('calibration', description='Generated tagged profile vision.json'),
        DeclareLaunchArgument('world', default_value='',
                              description='Optional perception-only world; no robot/controllers are spawned'),
        OpaqueFunction(function=setup),
    ])
