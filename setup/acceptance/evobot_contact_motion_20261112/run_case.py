"""One preregistered original/candidate arm. Run inside the existing image."""
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
import xml.etree.ElementTree as ET

import yaml
from ament_index_python.packages import get_package_share_directory
from task_launch import materialize as materialize_launch

arm = sys.argv[1]
if arm not in ('control', 'contact'):
    raise SystemExit('expected control or contact')
run_label = sys.argv[2] if len(sys.argv) > 2 else arm
if not run_label.replace('_', '').isalnum():
    raise SystemExit('run label must contain only letters, digits or underscores')
original = Path('/opt/flexcell/repo')
candidate = Path('/candidate')
runtime = candidate
sys.path.insert(0,str(candidate/'scripts'))
out = Path('/artifacts') / run_label
out.mkdir(exist_ok=False)
lock = open('/artifacts/simulation.lock', 'a')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', PYTHONUNBUFFERED='1', GZ_PARTITION='evobot-feedback-' + run_label,
                  ROS_DOMAIN_ID=str(int(sys.argv[3])) if len(sys.argv) > 3 else '190', ROS_LOG_DIR=str(out / 'ros_logs'),
                  FLEXCELL_PHYSICS_STEP_LOG=str(out / 'physics.jsonl'),
                  FLEXCELL_CONTACT_STEP_LOG=str(out / 'contacts.jsonl'))
os.environ['PYTHONPATH'] = ':'.join([str(runtime / 'src/flexcell/flexcell_skills'),
    str(runtime / 'src/flexcell/flexcell_skills/flexcell_skills/contracts'),
    os.environ.get('PYTHONPATH', '')])
sys.path[:0] = [str(runtime / 'src/flexcell/flexcell_skills'), str(original / 'scripts')]
import sim_profile
from flexcell_skills import common, push_server
from flexcell_skills.contracts import push, push_recover
from flexcell_skills import contact_geometry, contact_motion, contact_receipt, contact_trace

task = original / 'benchmark/tasks/t08_dev/T08-push-seed2000.json'
spec = json.loads(task.read_text())
geometry = json.loads(Path('/artifacts/geometry.json').read_text())
provenance = dict(arm=arm, run_label=run_label, image_base_revision=os.environ.get('FLEXCELL_SOURCE_REV'),
                  runtime_overlay=True, sources={})
for module in (sim_profile, common, push_server, push, push_recover,
               contact_geometry, contact_motion, contact_receipt, contact_trace):
    p = Path(module.__file__)
    provenance['sources'][module.__name__] = dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
for p in (candidate / 'scripts/diagnostics/record_world_state.py',
          candidate / 'src/flexcell/flexcell_skills/run_contact_push.py',
          candidate / 'setup/acceptance/evobot_contact_motion_20261112/record_receipts.py',
          candidate / 'setup/acceptance/evobot_contact_motion_20261112/task_launch.py',
          candidate / 'scripts/task_world.py', Path(__file__)):
    provenance['sources'][p.name] = dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
provenance['model'] = json.loads(Path('/artifacts/model/sources.json').read_text())
(out / 'provenance.json').write_text(json.dumps(provenance, indent=2))
subprocess.run([sys.executable, str(original / 'benchmark/tools/check_ros_interfaces.py')],
               check=True, stdout=(out / 'interfaces.log').open('x'), stderr=subprocess.STDOUT)
sim_profile.profile(out / 'sim', 'velocity_servo', False, 'legacy', 0., None)
params = out / 'sim/params.yaml'
config = yaml.safe_load(params.read_text())
config['push_server'] = {'ros__parameters': {'log_dir': str(out / 'sim/skills'), 'use_sim_time': True}}
config['move_to_pose_server']['ros__parameters'].update(execution_timeout_s=60., default_deadline_ms=60000, max_deadline_ms=60000)
if arm == 'control':
    config['push_server']['ros__parameters'].update(safe_reposition_enabled=True, safe_reposition_hold_retreat_high=True, safe_reposition_min_height_m=geometry['minimum_measured_transit_z_m'])
params.write_text(yaml.safe_dump(config, sort_keys=False))

# Observational contact tracing, identical in both arms; no physical properties change.
world_path = out / 'sim/world.sdf'
from task_world import materialize, verify_initial
initialized = out/'sim/initialized.sdf'
manifest = materialize(world_path,initialized,spec['objects'])
(out/'world_initialization.json').write_text(json.dumps(manifest,indent=2))
world_path = initialized
tree = ET.parse(world_path)
world = tree.getroot().find('world')
physics = world.find("plugin[@name='gz::sim::systems::Physics']")
ET.SubElement(physics, 'contacts_entity_names').text = 'true'
trace = world.find("plugin[@name='flexcell::PhysicsTrace']")
ET.SubElement(trace, 'flush_each_step').text = 'true'
contact = ET.SubElement(world, 'plugin', name='flexcell::ContactTrace', filename='libflexcell_contact_trace.so')
ET.SubElement(contact, 'flush_each_step').text = 'true'
for model, collision in [('target_box_a', 'col'), ('target_box_b', 'col'), ('ground_plane', 'collision')]:
    watch = ET.SubElement(contact, 'watch')
    for key, value in [('model', model), ('link', 'link'), ('collision', collision)]:
        ET.SubElement(watch, key).text = value
    if model.startswith('target_box'):
        link = world.find("model[@name='%s']/link[@name='link']" % model)
        sensor = ET.SubElement(link, 'sensor', name='diagnostic_contacts', type='contact')
        ET.SubElement(sensor, 'always_on').text = 'true'
        ET.SubElement(sensor, 'update_rate').text = '500'
        ET.SubElement(ET.SubElement(sensor, 'contact'), 'collision').text = collision
tree.write(world_path, encoding='utf-8', xml_declaration=True)
provenance['world_sha256'] = hashlib.sha256(world_path.read_bytes()).hexdigest()
provenance['params_sha256'] = hashlib.sha256(params.read_bytes()).hexdigest()
(out / 'provenance.json').write_text(json.dumps(provenance, indent=2))


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


def truth(filename):
    state = {'objects': {}}
    for obj in spec['objects']:
        pose, error = common.sample_gz_pose(obj['name'])
        if pose is None:
            raise RuntimeError(error)
        x, y, z, w = pose[1]
        state['objects'][obj['name']] = [*pose[0], math.atan2(2*(w*z+x*y), 1-2*(y*y+z*z))]
    (out / filename).write_text(json.dumps(state, indent=2))
    return state


stack = recorder = joints = consumer = None
status = dict(arm=arm, status='STARTING', physical_capability_claim=False)
try:
    task_launch,launch_manifest=materialize_launch(
        Path(get_package_share_directory('flexcell_skills'))/'launch',out/'sim')
    (out/'launch_manifest.json').write_text(json.dumps(launch_manifest,indent=2))
    stack = subprocess.Popen(['ros2', 'launch', str(task_launch),
                              'world:=' + str(world_path), 'params_file:=' + str(params), 'camera:=false'],
                             stdout=(out / 'stack.log').open('x'), stderr=subprocess.STDOUT, start_new_session=True)
    import rclpy
    from rclpy.action import ActionClient
    from rclpy.node import Node
    from flexcell_interfaces.action import Observe, PushObject, MoveToPose
    rclpy.init()
    node = Node('return_probe_startup')
    clients = [ActionClient(node, action, name) for action, name in
               [(Observe, '/observe'), (PushObject, '/push_object'), (MoveToPose, '/move_to_pose')]]
    deadline = time.monotonic() + 100
    while not all(c.server_is_ready() for c in clients):
        if stack.poll() is not None or time.monotonic() >= deadline:
            raise RuntimeError('startup failed')
        rclpy.spin_once(node, timeout_sec=.1)
    node.destroy_node()
    rclpy.shutdown()
    subprocess.run(['ps','-eo','pid,ppid,pcpu,stat,args'],check=True,
                   stdout=(out/'startup_processes.txt').open('x'))
    time.sleep(5)
    before = truth('gt_before.json')
    verify_initial({n:p for n,p in before['objects'].items()},spec['objects'])
    for obj in spec['objects']:
        if math.dist(before['objects'][obj['name']][:3], obj['initial_pose'][:3]) > .001:
            raise RuntimeError('initial pose disagrees with declared development task')
    recorder = subprocess.Popen([sys.executable, str(candidate / 'scripts/diagnostics/record_world_state.py'),
                                 '--out', str(out / 'worldstate'), '--duration', '560',
                                 '--observe-period', '.5', '--stop-file', str(out / 'stop_recording')],
                                stdout=(out / 'recorder.log').open('x'), stderr=subprocess.STDOUT, start_new_session=True)
    joints = subprocess.Popen([sys.executable, str(candidate / 'scripts/diagnostics/record_joints.py'),
                               str(out / 'joints.jsonl'), str(out / 'stop_recording')],
                              stdout=(out / 'joints.log').open('x'), stderr=subprocess.STDOUT, start_new_session=True)
    # Include cold interpreter imports AND the recorder's own 15 s request timeout.
    deadline = time.monotonic() + 60
    while True:
        try:
            observed = [json.loads(line) for line in (out / 'worldstate/world_state.jsonl').read_text().splitlines()]
            joint_rows = [json.loads(line) for line in (out / 'joints.jsonl').read_text().splitlines()]
            if (sum(r['channel'] == 'topic' and not r['issues'] for r in observed) >= 2
                    and any('gripper_left_joint' in r['name'] for r in joint_rows)):
                break
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        if time.monotonic() >= deadline or recorder.poll() is not None or joints.poll() is not None:
            raise RuntimeError('required observation stream missing; no push dispatched')
        time.sleep(.1)
    trial = out / 'trial'
    if arm == 'control':
        driver = [sys.executable,str(candidate/'src/flexcell/flexcell_skills/run_push_feedback.py'),str(task),str(trial),'--attempts','2','--motion-profile','demo_veryslow']
    else:
        consumer = subprocess.Popen([sys.executable,
            str(candidate/'setup/acceptance/evobot_contact_motion_20261112/record_receipts.py'),
            str(out/'receipt_consumer.jsonl'),str(out/'stop_recording')],
            stdout=(out/'receipt_consumer.log').open('x'),stderr=subprocess.STDOUT,start_new_session=True)
        driver = [sys.executable,str(candidate/'src/flexcell/flexcell_skills/run_contact_push.py'),str(task),str(trial),'--attempts','2']
    result = subprocess.run(driver,
                            stdout=(out / 'decision.log').open('x'), stderr=subprocess.STDOUT, timeout=500)
    status['driver_exit'] = result.returncode
    time.sleep(2)
    final = truth('gt_after.json')
    (out / 'stop_recording').touch(exist_ok=False)
    recorder.wait(timeout=20)
    joints.wait(timeout=10)
    if consumer is not None:consumer.wait(timeout=10)
    status['status'] = 'EXECUTED'
except Exception as exc:
    status.update(status='FAILED', error='%s: %s' % (type(exc).__name__, exc))
    raise
finally:
    stop(recorder)
    stop(joints)
    stop(consumer)
    stop(stack)
    (out / 'run_status.json').write_text(json.dumps(status, indent=2))

# Use the existing recorder and evaluator unchanged; raw source files stay archived.
pusher_links = ['open_manipulator_x::%s::%s_collision' % (name, name)
               for name in ['link5', 'gripper_left_link', 'gripper_right_link']]
subprocess.run([sys.executable, str(original / 'benchmark/evidence/recorder.py'),
    '--physics-log', str(out / 'physics.jsonl'), '--contact-log', str(out / 'contacts.jsonl'),
    '--joint-log', str(out / 'joints.jsonl'), '--task', str(task), '--task-id', spec['task_id'],
    '--run-id', 'feedback-' + run_label, '--target', 'target_box_a', '--protected', 'target_box_b',
    '--rest-height', str(spec['objects'][0]['initial_pose'][2]), '--pusher-links', *pusher_links,
    '--gripper-joint', 'gripper_left_joint', '--out', str(out / 'evidence_bundle.json')],
    check=True, stdout=(out / 'bundle_build.log').open('x'), stderr=subprocess.STDOUT)
bundle = json.loads((out / 'evidence_bundle.json').read_text())
final['evidence'] = bundle
final['trajectory'] = {name: {'max_z_m': max(s[5] for s in entry['samples'])}
                       for name, entry in bundle['objects'].items() if entry['samples']}
(out / 'observation.json').write_text(json.dumps(final, indent=2))
subprocess.run([sys.executable, str(original / 'benchmark/evaluators/evaluate.py'),
                str(task), str(out / 'observation.json')], check=True,
               stdout=(out / 'verdict.json').open('x'), stderr=(out / 'evaluator.stderr').open('x'))
if not (out / 'sim/skills/push.jsonl').is_file():
    (out / 'legacy_push_log_absent.json').write_text(json.dumps({
        'legacy_push_log_present': False, 'expected_for_contact_adapter': arm == 'contact',
        'driver_exit': result.returncode,
        'constrained_actions_recorded_in': 'trial/events.jsonl' if arm == 'contact' else None}))
print(arm, 'complete; inspect contact receipts and frozen acceptance separately')
