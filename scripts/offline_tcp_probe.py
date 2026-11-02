#!/usr/bin/env python3
"""Reproduce recorded TCP-offset planning with no simulator or actuator client."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    from ament_index_python.packages import get_package_prefix, get_package_share_directory
    from moveit_configs_utils import MoveItConfigsBuilder
    import yaml

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-base', type=Path, required=True)
    parser.add_argument('--executable', type=Path)
    args = parser.parse_args()
    out = args.out_base / ('offline-tcp-' + uuid.uuid4().hex[:12])
    out.mkdir(parents=True, exist_ok=False)
    fixture_path = ROOT / 'infra/tcp-frozen-fixture.json'
    fixture = json.loads(fixture_path.read_text())
    (out / 'fixture.json').write_bytes(fixture_path.read_bytes())
    description = Path(get_package_share_directory('open_manipulator_description'))
    model = description / 'urdf/open_manipulator_x/open_manipulator_x.urdf.xacro'
    config = (MoveItConfigsBuilder('open_manipulator_x', package_name='open_manipulator_moveit_config')
        .robot_description(file_path=str(model), mappings={'use_sim': 'true'})
        .robot_description_semantic(file_path='config/open_manipulator_x/open_manipulator_x.srdf')
        .joint_limits(file_path='config/open_manipulator_x/joint_limits.yaml')
        .robot_description_kinematics(file_path='config/open_manipulator_x/kinematics.yaml')
        .planning_pipelines(pipelines=['ompl']).to_moveit_configs().to_dict())
    config.update(use_sim_time=False, probe_output=str(out / 'report.json'))
    for key in ('frozen_joint_names', 'frozen_joint_positions', 'tcp_pose'):
        config[key] = fixture[key]
    params = out / 'params.yaml'
    params.write_text(yaml.safe_dump({'flexcell_tcp_probe': {'ros__parameters': config}}))
    executable = args.executable or Path(get_package_prefix('flexcell_mtc')) / 'lib/flexcell_mtc/tcp_sampler_probe'
    with (out / 'probe.log').open('x') as log:
        result = subprocess.run([str(executable), '--ros-args', '--params-file', str(params)],
            stdout=log, stderr=subprocess.STDOUT, timeout=90,
            env=dict(os.environ, FLEXCELL_MTC_PLAN_EVIDENCE_DIR=str(out / 'wire-evidence')))
    if result.returncode:
        print((out / 'probe.log').read_text()[-7000:])
        raise RuntimeError('offline probe failed; full evidence retained at ' + str(out))
    report = json.loads((out / 'report.json').read_text())
    assert report['status'] == 'OFFLINE_TCP_PASS' and report['robot_tasks'] == 0
    from rclpy.serialization import deserialize_message
    from flexcell_interfaces.srv import PlanManipulation
    from moveit_msgs.msg import PlanningScene
    from rcl_interfaces.msg import ParameterEvent
    records = list((out / 'wire-evidence').iterdir())
    assert len(records) == 1
    record = records[0]
    request = deserialize_message((record / 'request.cdr').read_bytes(), PlanManipulation.Request)
    response = deserialize_message((record / 'response.cdr').read_bytes(), PlanManipulation.Response)
    scene = deserialize_message((record / 'scene.cdr').read_bytes(), PlanningScene)
    parameters = deserialize_message((record / 'parameters.cdr').read_bytes(), ParameterEvent)
    assert request.operation == 'PLACE' and request.attached_object_targets
    assert len(request.targets) == len(response.trajectories) == len(response.executor_targets) == 3 and response.success
    assert scene.robot_state.attached_collision_objects[0].object.id == 'target_box_a'
    assert any(p.name == 'robot_description' for p in parameters.changed_parameters)
    assert 'flexcell_object_tcp' in (record / 'planning_model.urdf').read_text()
    assert 'flexcell_object_arm' in (record / 'planning_model.srdf').read_text()
    assert report['bad_evidence_path_rejected'] is True
    print(json.dumps(dict(out=str(out), **report), indent=2))


if __name__ == '__main__':
    main()
