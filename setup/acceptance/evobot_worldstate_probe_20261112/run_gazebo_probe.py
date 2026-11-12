"""One owned Gazebo process group; original push recovery, added acquisition only."""
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

repo = Path(os.environ['FLEXCELL_REPO'])
diag = Path('/diagnostics')
out = Path('/artifacts/gazebo')
out.mkdir(exist_ok=False)
lock = open('/tmp/evobot-gazebo.lock', 'a')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
os.environ['PYTHONUNBUFFERED'] = '1'
os.environ['PYTHONPATH'] = ':'.join([
    str(repo / 'src/flexcell/flexcell_skills'),
    str(repo / 'src/flexcell/flexcell_skills/flexcell_skills/contracts'),
    os.environ.get('PYTHONPATH', '')])
sys.path.insert(0, str(repo / 'scripts'))
sys.path.insert(0, str(repo / 'src/flexcell/flexcell_skills'))
import sim_profile
from flexcell_skills import observe_server, push_server, common

provenance = dict(kind='ONE_GAZEBO_WORLDSTATE_PROBE', source_revision=os.getenv('FLEXCELL_SOURCE_REV'),
                  context={k: os.getenv(k) for k in ['ROS_DOMAIN_ID','RMW_IMPLEMENTATION','GZ_PARTITION']},
                  sources={})
for module in (sim_profile, observe_server, push_server):
    path = Path(module.__file__)
    provenance['sources'][module.__name__] = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
(out / 'provenance.json').write_text(json.dumps(provenance, indent=2))
subprocess.run([sys.executable, str(repo / 'benchmark/tools/check_ros_interfaces.py')],
               check=True, stdout=(out / 'interfaces.log').open('x'), stderr=subprocess.STDOUT)
sim_profile.profile(out / 'sim', 'velocity_servo', False, 'legacy', 0., None)

def stop(proc):
    if proc is None or proc.poll() is not None:
        return
    for sig, wait in ((signal.SIGINT, 12), (signal.SIGTERM, 4), (signal.SIGKILL, 3)):
        try:
            os.killpg(proc.pid, sig)
            proc.wait(timeout=wait)
            return
        except ProcessLookupError:
            return
        except subprocess.TimeoutExpired:
            pass

def ground_truth(name):
    state = dict(objects={})
    for obj in ['target_box_a', 'target_box_b']:
        pose, err = common.sample_gz_pose(obj)
        if pose is None:
            raise RuntimeError('ground truth unavailable: ' + str(err))
        x, y, z, w = pose[1]
        yaw = math.atan2(2 * (w*z + x*y), 1 - 2 * (y*y + z*z))
        state['objects'][obj] = [*pose[0], yaw]
    (out / name).write_text(json.dumps(state, indent=2))

stack = recorder = None
try:
    stack = subprocess.Popen(['ros2','launch','flexcell_skills','trusted_sim.launch.py',
                              'world:=' + str(out / 'sim/world.sdf'),
                              'params_file:=' + str(out / 'sim/params.yaml'), 'camera:=false'],
                             stdout=(out / 'stack.log').open('x'), stderr=subprocess.STDOUT,
                             start_new_session=True)
    import rclpy
    from rclpy.action import ActionClient
    from rclpy.node import Node
    from flexcell_interfaces.action import Observe, PushObject, MoveToPose
    rclpy.init()
    node = Node('probe_startup')
    clients = [ActionClient(node, action, name) for action, name in
               [(Observe, '/observe'), (PushObject, '/push_object'), (MoveToPose, '/move_to_pose')]]
    deadline = time.monotonic() + 100
    while not all(client.server_is_ready() for client in clients):
        if stack.poll() is not None or time.monotonic() > deadline:
            raise RuntimeError('simulation startup failed; inspect stack.log')
        rclpy.spin_once(node, timeout_sec=.1)
    node.destroy_node()
    rclpy.shutdown()
    time.sleep(3)
    # No Observe call has occurred: a publisher can exist without a single sample.
    passive = subprocess.run([sys.executable, str(diag / 'record_world_state.py'),
                              '--out', str(out / 'passive'), '--duration','5'],
                             stdout=(out / 'passive.log').open('x'), stderr=subprocess.STDOUT, timeout=12)
    ground_truth('gt_before.json')
    recorder = subprocess.Popen([sys.executable, str(diag / 'record_world_state.py'),
                                 '--out',str(out / 'active'),'--duration','360',
                                 '--observe-period','.5','--stop-file',str(out / 'stop')],
                                stdout=(out / 'active.log').open('x'),stderr=subprocess.STDOUT,
                                start_new_session=True)
    deadline = time.monotonic() + 25
    while True:
        path = out / 'active/world_state.jsonl'
        if path.exists():
            try:
                records = [json.loads(line) for line in path.read_text().splitlines()]
                usable = [r for r in records if r['channel'] == 'topic' and not r['issues']]
                if len(usable) >= 2:
                    break
            except json.JSONDecodeError:  # The recorder may be halfway through its latest write.
                pass
        if recorder.poll() is not None or time.monotonic() > deadline:
            raise RuntimeError('active acquisition failed before motion')
        time.sleep(.2)
    trial = out / 'trial'
    trial.mkdir()
    task = repo / 'benchmark/tasks/t08_dev/T08-push-seed2000.json'
    result = subprocess.run([sys.executable, str(repo / 'src/flexcell/flexcell_skills/run_push_recovery.py'),
                             str(task), str(trial), '0.0200','2'],
                            stdout=(out / 'decision.log').open('x'), stderr=subprocess.STDOUT, timeout=300)
    ground_truth('gt_after.json')
    time.sleep(2)
    (out / 'stop').touch(exist_ok=False)
    recorder.wait(timeout=20)
    subprocess.run([sys.executable, str(repo / 'benchmark/evaluators/evaluate.py'),
                    str(task), str(out / 'gt_after.json')],
                   stdout=(out / 'verdict.json').open('x'), stderr=(out / 'evaluator.stderr').open('x'), timeout=20)
    print('Probe completed. Inspect physical results separately from acquisition.')
finally:
    stop(recorder)
    stop(stack)
