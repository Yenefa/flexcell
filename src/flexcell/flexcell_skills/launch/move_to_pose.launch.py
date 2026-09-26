from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    params_file = PathJoinSubstitution(
        [FindPackageShare('flexcell_skills'), 'config', 'move_to_pose.yaml']
    )
    return LaunchDescription([
        DeclareLaunchArgument('params_file', default_value=params_file),
        Node(
            package='flexcell_skills',
            executable='move_to_pose_server',
            name='move_to_pose_server',
            output='screen',
            parameters=[
                LaunchConfiguration('params_file'),
                {'use_sim_time': True},
            ],
        ),
    ])
