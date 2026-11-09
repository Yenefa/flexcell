from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    params_file = PathJoinSubstitution(
        [FindPackageShare('flexcell_skills'), 'config', 'week1.yaml']
    )
    # NOTE (bugfix, jev runtime finding): the yaml path must be passed as the
    # parameters-list item itself - the old `{'params_file': ...}` dict form
    # passed the PATH as a literal node parameter, so week1.yaml was never
    # actually loaded (its values happened to match the code defaults, which
    # masked this for weeks).  Mixing a substitution and a dict in one
    # parameters list is also rejected by launch_ros (TypeError), so the
    # ONLY supported override path is a complete yaml file.
    return LaunchDescription([
        DeclareLaunchArgument('params_file', default_value=params_file),
        Node(package='flexcell_skills', executable='observe_server',
             name='observe_server', output='screen',
             parameters=[LaunchConfiguration('params_file')]),
        Node(package='flexcell_skills', executable='pick_server',
             name='pick_server', output='screen',
             parameters=[LaunchConfiguration('params_file')]),
        Node(package='flexcell_skills', executable='place_server',
             name='place_server', output='screen',
             parameters=[LaunchConfiguration('params_file')]),
        Node(package='flexcell_skills', executable='verify_server',
             name='verify_server', output='screen',
             parameters=[LaunchConfiguration('params_file')]),
        Node(package='flexcell_skills', executable='task_fsm_server',
             name='task_fsm_server', output='screen',
             parameters=[LaunchConfiguration('params_file')]),
        Node(package='flexcell_skills', executable='carry_server',
             name='carry_server', output='screen',
             parameters=[LaunchConfiguration('params_file')]),
    ])
