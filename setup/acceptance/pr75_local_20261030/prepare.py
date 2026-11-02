"""Reconstruct a diagnostic pose from preserved bytes, never an exact scene claim."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import zipfile

import yaml
import xacro
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import JointState

out = Path(os.environ['FC_OUT']) / 'ik-probe'
out.mkdir(exist_ok=False)
archive = out.parent / 'ci-joint-failed-c2583ae.zip'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == '402775c6b03f1780ceb660cb50da6c584c20ebac56a9e275f256e0f0b4c761e5'
with zipfile.ZipFile(archive) as z:
    place_path = next(n for n in z.namelist() if n.endswith('skills/place.jsonl'))
    place = json.loads(z.read(place_path).decode().splitlines()[0])
    start_ns = round((place['wall_ts'] - place['elapsed_ms'] / 1000) * 1e9)
    db_name = next(n for n in z.namelist() if n.endswith('raw_0.db3'))
    db_path = out / 'raw_0.db3'
    db_path.write_bytes(z.read(db_name))
    params = yaml.safe_load(z.read(next(n for n in z.namelist() if n.endswith('params.yaml'))))
db = sqlite3.connect(f'file:{db_path.as_posix()}?mode=ro', uri=True)
stamp, data = db.execute('SELECT timestamp,data FROM messages WHERE topic_id=(SELECT id FROM topics WHERE name=?) ORDER BY ABS(timestamp-?) LIMIT 1', ('/joint_states', start_ns)).fetchone()
joint = deserialize_message(data, JointState)
box = place['planning_object_pose']
place_params = params['place_server']['ros__parameters']
hover = [0.12, -0.15, 0.0175 + place_params['release_clearance_m'] + place_params['release_hover_m']]
pinned = out.parent / 'pinned-open-manipulator'
prefix = out / 'model-prefix'
for package in ['open_manipulator_description', 'open_manipulator_bringup', 'open_manipulator_moveit_config']:
    resource = prefix / 'share/ament_index/resource_index/packages' / package
    resource.parent.mkdir(parents=True, exist_ok=True)
    resource.touch()
    (prefix / 'share' / package).symlink_to(pinned / package, target_is_directory=True)
os.environ['AMENT_PREFIX_PATH'] = str(prefix) + ':' + os.environ['AMENT_PREFIX_PATH']
description = pinned / 'open_manipulator_description'
robot = xacro.process_file(str(description / 'urdf/open_manipulator_x/open_manipulator_x.urdf.xacro'), mappings={'use_sim': 'true'}).toxml()
semantic = (pinned / 'open_manipulator_moveit_config/config/open_manipulator_x/open_manipulator_x.srdf').read_text()
kinematics = yaml.safe_load((pinned / 'open_manipulator_moveit_config/config/open_manipulator_x/kinematics.yaml').read_text())
configuration = {'robot_description': robot, 'robot_description_semantic': semantic,
                 'robot_description_kinematics': kinematics,
                 'probe.names': list(joint.name), 'probe.positions': list(joint.position),
                 'probe.box_pose': box, 'probe.hover': hover}
(out / 'probe-params.yaml').write_text(yaml.safe_dump({'pr75_ik_probe': {'ros__parameters': configuration}}))
report = {'status': 'RECONSTRUCTED_OFFLINE_GEOMETRY', 'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
          'place_record': place_path, 'joint_bag_timestamp_ns': stamp, 'inferred_place_start_ns': start_ns,
          'joint_timestamp_difference_ms': (stamp-start_ns)/1e6,
          'box_pose': box, 'hover': hover, 'names': list(joint.name), 'positions': list(joint.position),
          'pinned_robotis_revision': '17efe42bd1df178fa44d49c43250fc4304343dbb',
          'urdf_sha256': hashlib.sha256(robot.encode()).hexdigest(),
          'srdf_sha256': hashlib.sha256(semantic.encode()).hexdigest(),
          'limits': 'Exact planning scene and planner request were not recorded. No collision scene, actuator or simulator; reconstructed point-sampling diagnostic only.'}
(out / 'fixture.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
