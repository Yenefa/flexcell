"""Run old/new CLI against synthetic ROS plumbing; never contact a robot.

From the repo root: PYTHONPATH=src/flexcell/flexcell_skills python3 \
    setup/acceptance/grasp_probe_20261008/reproduce_probe.py
"""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
from types import SimpleNamespace as NS
from unittest.mock import patch

BASE = 'c79e0c672c95e2d9cd04112ef42b65e4c67e1845'
ROOT = Path(__file__).resolve().parents[3]
SOURCE = 'setup/111_grasp_probe.py'


def pose(z=.0175, measured=True):
    return NS(position=NS(x=.20, y=-.18, z=z),
              orientation=NS(x=0., y=0., z=0., w=1. if measured else 0.))


def fixture(mode):
    good = mode != 'ghost'
    return NS(outcome=0, error_code=0, status=1 if good else 0,
              grasp_attached=good, object_pose_before=pose(measured=good),
              object_pose_after=pose(z=.11 if good else 0., measured=good),
              evidence_id='synthetic-pick', detail='synthetic result')


class Future:
    def __init__(self, value, complete=True):
        self.value, self.complete = value, complete

    def done(self):
        return self.complete

    def result(self):
        return self.value if self.complete else None


class Handle:
    accepted = True
    goal_id = NS(uuid=list(range(16)))

    def __init__(self, reply, complete):
        self.future = Future(reply, complete)

    def get_result_async(self):
        return self.future

    def cancel_goal_async(self):
        return Future(NS(goals_canceling=[self.goal_id]))


class Executor:
    def add_node(self, node):
        pass

    def spin_until_future_complete(self, future, timeout_sec):
        pass

    def shutdown(self):
        pass


def run(source, mode, out):
    counts = dict(picks=0, place_targets=[])

    class Node:
        def __init__(self, name):
            pass

        def destroy_node(self):
            pass

    class Client:
        def __init__(self, node, interface, action):
            self.action = action

        def wait_for_server(self, timeout_sec):
            return True

        def send_goal_async(self, goal):
            if self.action == '/pick_object':
                counts['picks'] += 1
                return Future(Handle(NS(status=4, result=fixture(mode)),
                    not (mode == 'timeout' and counts['picks'] == 1)))
            p = goal.place_pose.pose.position
            counts['place_targets'].append([p.x, p.y, p.z])
            result = NS(outcome=0, error_code=0, status=1, released=True,
                        object_pose_after=pose(), evidence_id='synthetic-place', detail='synthetic place')
            return Future(Handle(NS(status=4, result=result), True))

    def module(name, **attrs):
        result = types.ModuleType(name)
        result.__dict__.update(attrs)
        return result

    fake = {
        'rclpy': module('rclpy', init=lambda: None, shutdown=lambda: None, ok=lambda: True),
        'rclpy.action': module('rclpy.action', ActionClient=Client),
        'rclpy.node': module('rclpy.node', Node=Node),
        'rclpy.executors': module('rclpy.executors', SingleThreadedExecutor=Executor),
        'flexcell_interfaces.action': module('flexcell_interfaces.action',
            PickObject=NS(Goal=NS), PlaceObject=NS(Goal=NS)),
        'geometry_msgs.msg': module('geometry_msgs.msg',
            PoseStamped=lambda: NS(header=NS(frame_id=''), pose=pose())),
    }
    namespace = {'__file__': str(ROOT/SOURCE), '__name__': 'offline_probe_reproduction'}
    argv = ['probe', '--trials', '2', '--object', 'target_box_b', '--out', str(out),
            '--settle-s', '0', '--release-s', '0']
    stdout = io.StringIO()
    with patch.dict(sys.modules, fake), patch.object(sys, 'argv', argv), \
            patch('subprocess.run', return_value=NS(returncode=0, stdout='{"ok": true}', stderr='')), \
            patch('time.sleep', lambda _: None), contextlib.redirect_stdout(stdout):
        exec(compile(source, str(ROOT/SOURCE), 'exec'), namespace)
        exit_code = namespace['main']()
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    return dict(exit_code=exit_code, dispatch=counts, rows=rows, stdout=stdout.getvalue())


def main():
    old = subprocess.check_output(['git', 'show', BASE+':'+SOURCE], cwd=ROOT, text=True)
    new = (ROOT/SOURCE).read_text()
    cases = []
    with tempfile.TemporaryDirectory() as directory:
        for mode in ['ghost', 'timeout', 'b_position']:
            before = run(old, mode, Path(directory)/(mode+'-before.jsonl'))
            after = run(new, mode, Path(directory)/(mode+'-after.jsonl'))
            if mode == 'b_position':
                assert before['dispatch']['place_targets'][0] == [.22, 0., .0175]
                assert after['dispatch']['place_targets'][0] == [.20, -.18, .0175]
            else:
                assert before['exit_code'] == 0 and after['exit_code'] == 1
                assert before['dispatch']['picks'] == 2 and after['dispatch']['picks'] == 1
            cases.append(dict(mode=mode, before=before, after=after))
    output = Path(__file__).with_name('reproduction.json')
    output.write_text(json.dumps(dict(source_base=BASE,
        kind='synthetic CLI reproduction; no ROS/Gazebo/model/robot calls', cases=cases), indent=2)+'\n')
    print('3 old/new CLI reproductions PASS: ghost, timeout, B placement')


if __name__ == '__main__':
    main()
