"""The capability package works when ROS, task execution and development are absent."""
from pathlib import Path
import subprocess
import sys


def test_geometry_and_telemetry_work_without_execution_or_development_packages(tmp_path):
    code = '''
import importlib.abc
import sys
from pathlib import Path

class RefuseExecution(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {
            'flexcell_skills', 'runtime', 'evolution', 'development_skills',
            'rclpy', 'flexcell_interfaces', 'moveit_msgs',
        }:
            raise AssertionError('physical model imported execution/development: ' + fullname)

sys.meta_path.insert(0, RefuseExecution())
sys.path.insert(0, sys.argv[1])
from flexcell_capabilities.contact_geometry import ContactGeometry
from flexcell_capabilities.contact_trace import JsonTail, NativeContact
model = ContactGeometry.__new__(ContactGeometry)
pose = model.frames([0., 0., 0., 0.])['end_effector_link']
assert pose.shape == (4, 4)
directory = Path(sys.argv[2])
assert JsonTail(directory / 'absent.jsonl').read() == []
assert NativeContact(directory, 'box', {}).latest is None
assert list(directory.iterdir()) == []
'''
    reply = subprocess.run(
        [sys.executable, '-I', '-c', code, str(Path(__file__).parents[1]), str(tmp_path)],
        capture_output=True, text=True, timeout=20,
    )
    assert reply.returncode == 0, reply.stderr
