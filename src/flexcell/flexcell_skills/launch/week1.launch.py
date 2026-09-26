from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    params_file = PathJoinSubstitution(
        [FindPackageShare('flexcell_skills'), 'config', 'week1.yaml']
    )
    common = {'params_file': params_file, 'use_sim_time': True}

    return LaunchDescription([
        DeclareLaunchArgument('params_file', default_value=params_file),
        Node(package='flexcell_skills', executable='observe_server',
             name='observe_server', output='screen', parameters=[common]),
        Node(package='flexcell_skills', executable='pick_server',
             name='pick_server', output='screen', parameters=[common]),
        Node(package='flexcell_skills', executable='place_server',
             name='place_server', output='screen', parameters=[common]),
        Node(package='flexcell_skills', executable='verify_server',
             name='verify_server', output='screen', parameters=[common]),
        Node(package='flexcell_skills', executable='task_fsm_server',
             name='task_fsm_server', output='screen', parameters=[common]),
        Node(package='flexcell_skills', executable='carry_server',
             name='carry_server', output='screen', parameters=[common]),
    ])
