"""The camera info must reach the documented ROS topic, not an empty one."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
LAUNCH = ROOT / 'src/flexcell/flexcell_skills/launch/trusted_sim.launch.py'


def test_camera_info_bridge_reads_the_gz_topic_and_keeps_the_ros_name():
    source = LAUNCH.read_text()
    assert "'/flexcell/camera/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo'" in source
    assert "'/flexcell/camera/camera_info:=/flexcell/camera/rgb/camera_info'" in source
    assert 'bridges + remaps' in source


def test_the_empty_camera_info_bridge_is_not_kept():
    source = LAUNCH.read_text()
    assert "'/flexcell/camera/rgb/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo'" not in source
