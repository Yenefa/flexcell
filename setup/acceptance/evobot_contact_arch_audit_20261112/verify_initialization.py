"""One synthetic fixture initialization check; no pushing or capability claim."""
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

sys.path[:0] = ['/candidate/scripts','/candidate/src/flexcell/flexcell_skills']
import sim_profile
from task_world import LayoutError,materialize,verify_initial
from flexcell_skills import common

out = Path('/artifacts/initialization_probe')
out.mkdir(exist_ok=False)
objects = [dict(name='target_box_a',size=[.035]*3,initial_pose=[.23,.015,.0175,.2]),
           dict(name='target_box_b',size=[.035]*3,initial_pose=[.20,-.17,.0175,-.1])]
os.environ.update(ROS_DOMAIN_ID='204',GZ_PARTITION='evobot-architecture-initialization',
                  ROS_LOG_DIR=str(out/'ros_logs'),FLEXCELL_PHYSICS_STEP_LOG=str(out/'physics.jsonl'),
                  PYTHONPATH='/candidate/src/flexcell/flexcell_skills:'+os.environ.get('PYTHONPATH',''))
(out/'declared_public_fixture.json').write_text(json.dumps(objects,indent=2))
sim_profile.profile(out/'sim','velocity_servo',False,'legacy',0.,None)
world = out/'initialized_world.sdf'
manifest = materialize(out/'sim/world.sdf',world,objects)
(out/'initialization_manifest.json').write_text(json.dumps(manifest,indent=2))
stack = None
node = None
result = dict(kind='INITIALIZATION_ONLY_NOT_TASK_CAPABILITY',status='STARTING',
              physical_task_dispatched=False,independent_acceptance_claim=False)
try:
    stack = subprocess.Popen(['ros2','launch','flexcell_skills','trusted_sim.launch.py',
        'world:='+str(world),'params_file:='+str(out/'sim/params.yaml'),'camera:=false'],
        stdout=(out/'stack.log').open('x'),stderr=subprocess.STDOUT,start_new_session=True)
    import rclpy
    from rclpy.action import ActionClient
    from rclpy.node import Node
    from flexcell_interfaces.action import Observe
    from rosidl_runtime_py.convert import message_to_ordereddict
    rclpy.init()
    node = Node('declared_initial_world_probe')
    client = ActionClient(node,Observe,'/observe')
    end = time.monotonic()+100
    while not client.server_is_ready():
        if time.monotonic()>end or stack.poll() is not None:
            raise RuntimeError('Observe server unavailable')
        rclpy.spin_once(node,timeout_sec=.1)
    time.sleep(5)
    request = Observe.Goal();request.refresh=True;request.max_age_s=.5
    def wait(future):
        end = time.monotonic()+20
        while not future.done() and time.monotonic()<end:
            rclpy.spin_once(node,timeout_sec=.05)
        if not future.done():raise TimeoutError('Observe did not respond')
        return future.result()
    handle = wait(client.send_goal_async(request))
    if not handle.accepted:raise RuntimeError('Observe rejected')
    wrapped = wait(handle.get_result_async())
    if wrapped.status!=4 or wrapped.result.outcome!=0 or wrapped.result.error_code!=0:
        raise RuntimeError('Observe failed')
    state = message_to_ordereddict(wrapped.result.world_state)
    (out/'world_state.json').write_text(json.dumps(state,indent=2,allow_nan=False))
    observed = {}
    for obj in objects:
        pose,error = common.sample_gz_pose(obj['name'])
        if pose is None:raise RuntimeError(error)
        x,y,z,w = pose[1]
        observed[obj['name']] = [*pose[0],math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))]
    (out/'measured_initial.json').write_text(json.dumps(observed,indent=2))
    errors = verify_initial(observed,objects)
    original = json.loads(Path('/candidate/benchmark/tasks/t08_dev/T08-push-seed2000.json').read_text())['objects']
    try:
        verify_initial(observed,original)
    except LayoutError as exc:
        wrong_world_refused = str(exc)
    else:
        raise AssertionError('the old default scene was not refused')
    result.update(status='PASS',measured_errors=errors,old_default_world_guard_refusal=wrong_world_refused)
finally:
    if node is not None:
        node.destroy_node();rclpy.shutdown()
    if stack is not None and stack.poll() is None:
        for sig,timeout in [(signal.SIGINT,15),(signal.SIGTERM,5),(signal.SIGKILL,3)]:
            try:
                os.killpg(stack.pid,sig);stack.wait(timeout=timeout);break
            except ProcessLookupError:break
            except subprocess.TimeoutExpired:pass
    goals = {}
    for name in ['push.jsonl','move_to_pose.jsonl']:
        p = out/'sim/skills'/name
        goals[name] = len(p.read_text().splitlines()) if p.exists() else 0
    result['task_goal_log_rows'] = goals
    if any(goals.values()):result.update(status='FAILED_UNEXPECTED_MOTION_GOAL')
    (out/'result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
if result['status']!='PASS':raise SystemExit(2)
