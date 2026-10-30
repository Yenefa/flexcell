"""Check exact planner snapshots for one declared normal task."""
import hashlib
import json
from pathlib import Path

from rclpy.serialization import deserialize_message
from flexcell_interfaces.srv import PlanManipulation
from moveit_msgs.msg import PlanningScene


def verify_run(run, object_name):
    run = Path(run)
    snapshots = sorted((run / 'planner').glob('request-*'))
    if len(snapshots) != 2:
        raise ValueError('normal task must retain exactly one PICK and one PLACE request')
    identity = json.loads((run / 'identity.stdout').read_text())
    records = []
    for snapshot, operation in zip(snapshots, ('PICK', 'PLACE')):
        request = deserialize_message((snapshot / 'request.cdr').read_bytes(), PlanManipulation.Request)
        scene = deserialize_message((snapshot / 'scene.cdr').read_bytes(), PlanningScene)
        response = deserialize_message((snapshot / 'response.cdr').read_bytes(), PlanManipulation.Response)
        if request.operation != operation or request.object_name != object_name:
            raise ValueError('planner snapshot request differs from declared task')
        if not scene.robot_state.joint_state.name or not response.success or len(response.trajectories) != 3:
            raise ValueError('planner snapshot is incomplete or rejected')
        if (snapshot / 'source_revision.txt').read_text() != identity['source_revision']:
            raise ValueError('planner snapshot source revision differs from runtime identity')
        if not all((snapshot / name).stat().st_size for name in
                   ('robot_description.xml', 'robot_description_semantic.xml')):
            raise ValueError('planner snapshot robot description is missing')
        records.append(dict(operation=operation, directory=str(snapshot.relative_to(run)),
                            sha256={path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                    for path in sorted(snapshot.iterdir()) if path.is_file()}))
    return dict(status='PASS', requests=records)
