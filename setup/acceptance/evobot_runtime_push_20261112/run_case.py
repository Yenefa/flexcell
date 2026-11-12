"""Sequential physical task acceptance; Runtime is a separate public-only process."""
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

backend,label,domain,task_argument=sys.argv[1:]
if backend not in ('legacy','finger_tcp') or not label.replace('_','').isalnum():
    raise SystemExit('invalid backend or unique case label')
original=Path('/opt/flexcell/repo');candidate=Path('/candidate')
sys.path[:0]=[str(candidate),str(candidate/'scripts'),str(candidate/'src/flexcell/flexcell_skills')]
out=Path('/artifacts')/label;out.mkdir(exist_ok=False)
lock=open('/artifacts/simulation.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONUNBUFFERED='1',
    GZ_PARTITION='evobot-public-runtime-'+label,ROS_DOMAIN_ID=domain,
    ROS_LOG_DIR=str(out/'ros_logs'),FLEXCELL_PHYSICS_STEP_LOG=str(out/'physics.jsonl'),
    FLEXCELL_CONTACT_STEP_LOG=str(out/'contacts.jsonl'))
os.environ['PYTHONPATH']=':'.join([str(candidate),str(candidate/'src/flexcell/flexcell_skills'),
    os.environ.get('PYTHONPATH','')])
import sim_profile
from task_world import materialize,verify_initial
from runtime.planner.public_observation import reduce_to_public
from flexcell_skills import common

task=original/'benchmark/tasks/t08_dev/T08-push-seed2000.json' if task_argument=='original' else Path(task_argument)
spec=json.loads(task.read_text());public=reduce_to_public(spec)
(out/'public_task.json').write_text(json.dumps(public,indent=2))
target=next(iter(spec['expected_goal']['push']));protected=[o['name'] for o in spec['objects'] if o['name']!=target]
sources=[candidate/'runtime/run_public_push_task.py',candidate/'runtime/planner/push_task.py',
    candidate/'src/flexcell/flexcell_interfaces/action/ContactPush.action',Path(__file__),
    Path(__file__).with_name('task_launch.py')]
sources+=list((candidate/'src/flexcell/flexcell_skills/flexcell_skills').glob('contact_*.py'))
sources+=[candidate/'src/flexcell/flexcell_skills/flexcell_skills'/p for p in
    ['task_fsm_server.py','contracts/composite.py','contracts/contact_task.py','contracts/push.py','move_to_pose_server.py']]
provenance=dict(backend=backend,label=label,task_sha256=hashlib.sha256(task.read_bytes()).hexdigest(),
    image_source_revision=os.environ.get('FLEXCELL_SOURCE_REV'),
    sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
    model=json.loads(Path('/artifacts/model/sources.json').read_text()))
(out/'provenance.json').write_text(json.dumps(provenance,indent=2))
subprocess.run([sys.executable,str(original/'benchmark/tools/check_ros_interfaces.py')],check=True,
    stdout=(out/'interfaces.log').open('x'),stderr=subprocess.STDOUT)
sim_profile.profile(out/'sim','velocity_servo',False,'legacy',0.,None)
params=out/'sim/params.yaml';config=yaml.safe_load(params.read_text())
config['task_fsm_server']['ros__parameters'].update(use_sim_time=False,push_backend=backend,
    contact_task_motion_budget=40,contact_task_wall_s=600.)
config['move_to_pose_server']['ros__parameters'].update(execution_timeout_s=60.,default_deadline_ms=60000,max_deadline_ms=60000)
config['push_server']={'ros__parameters':dict(log_dir=str(out/'sim/skills'),use_sim_time=True,
    contact_height_m=.02,safe_reposition_enabled=True,safe_reposition_hold_retreat_high=True,
    safe_reposition_min_height_m=.18779145321586976)}
config['contact_push_server']={'ros__parameters':dict(use_sim_time=False,model_directory='/artifacts/model',
    native_directory=str(out),evidence_directory=str(out/'contact_goals'),
    tracked_objects=[o['name'] for o in spec['objects']])}
params.write_text(yaml.safe_dump(config,sort_keys=False))
world_path=out/'sim/initialized.sdf'
manifest=materialize(out/'sim/world.sdf',world_path,spec['objects'])
(out/'world_initialization.json').write_text(json.dumps(manifest,indent=2))
tree=ET.parse(world_path);world=tree.getroot().find('world')
ET.SubElement(world.find("plugin[@name='gz::sim::systems::Physics']"),'contacts_entity_names').text='true'
ET.SubElement(world.find("plugin[@name='flexcell::PhysicsTrace']"),'flush_each_step').text='true'
contact=ET.SubElement(world,'plugin',name='flexcell::ContactTrace',filename='libflexcell_contact_trace.so')
ET.SubElement(contact,'flush_each_step').text='true'
for name,collision in [(o['name'],'col') for o in spec['objects']]+[('ground_plane','collision')]:
    watch=ET.SubElement(contact,'watch')
    for key,value in [('model',name),('link','link'),('collision',collision)]:ET.SubElement(watch,key).text=value
    if name!='ground_plane':
        link=world.find("model[@name='%s']/link[@name='link']"%name)
        sensor=ET.SubElement(link,'sensor',name='diagnostic_contacts',type='contact')
        ET.SubElement(sensor,'always_on').text='true';ET.SubElement(sensor,'update_rate').text='500'
        ET.SubElement(ET.SubElement(sensor,'contact'),'collision').text=collision
tree.write(world_path,encoding='utf-8',xml_declaration=True)
provenance.update(world_sha256=hashlib.sha256(world_path.read_bytes()).hexdigest(),
    params_sha256=hashlib.sha256(params.read_bytes()).hexdigest())
(out/'provenance.json').write_text(json.dumps(provenance,indent=2))


def stop(proc):
    if proc is None or proc.poll() is not None:return
    for sig,timeout in ((signal.SIGINT,12),(signal.SIGTERM,4),(signal.SIGKILL,3)):
        try:os.killpg(proc.pid,sig);proc.wait(timeout=timeout);return
        except ProcessLookupError:return
        except subprocess.TimeoutExpired:pass


def truth(filename):
    state={'objects':{}}
    for obj in spec['objects']:
        pose,error=common.sample_gz_pose(obj['name'])
        if pose is None:raise RuntimeError(error)
        x,y,z,w=pose[1]
        state['objects'][obj['name']]=[*pose[0],math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))]
    (out/filename).write_text(json.dumps(state,indent=2));return state


stack=recorder=joints=driver=None;final=None
status=dict(backend=backend,label=label,status='STARTING',agent_claimed_success=None)
try:
    launch,manifest=materialize_launch(Path(get_package_share_directory('flexcell_skills'))/'launch',out/'sim',backend)
    (out/'launch_manifest.json').write_text(json.dumps(manifest,indent=2))
    stack=subprocess.Popen(['ros2','launch',str(launch),'world:='+str(world_path),
        'params_file:='+str(params),'camera:=false'],stdout=(out/'stack.log').open('x'),
        stderr=subprocess.STDOUT,start_new_session=True)
    import rclpy
    from rclpy.action import ActionClient
    from rclpy.node import Node
    from flexcell_interfaces.action import Observe,RunComposite,MoveToPose,ContactPush,PushObject
    rclpy.init();node=Node('public_runtime_startup_probe')
    clients=[ActionClient(node,action,name) for action,name in
        [(Observe,'/observe'),(RunComposite,'/run_composite'),(MoveToPose,'/move_to_pose'),
         (ContactPush,'/contact_push') if backend=='finger_tcp' else (PushObject,'/push_object')]]
    end=time.monotonic()+100.
    while not all(c.server_is_ready() for c in clients):
        if stack.poll() is not None or time.monotonic()>=end:raise RuntimeError('required task graph startup failed')
        rclpy.spin_once(node,timeout_sec=.1)
    node.destroy_node();rclpy.shutdown()
    subprocess.run(['ps','-eo','pid,ppid,pcpu,stat,args'],check=True,stdout=(out/'startup_processes.txt').open('x'))
    time.sleep(5)
    before=truth('gt_before.json');verify_initial(before['objects'],spec['objects'])
    if any(math.dist(before['objects'][o['name']][:3],o['initial_pose'][:3])>.001 for o in spec['objects']):
        raise RuntimeError('initial scene differs from declared validation task')
    recorder=subprocess.Popen([sys.executable,str(candidate/'scripts/diagnostics/record_world_state.py'),
        '--out',str(out/'worldstate'),'--duration','700','--observe-period','.5',
        '--stop-file',str(out/'stop_recording')],stdout=(out/'recorder.log').open('x'),
        stderr=subprocess.STDOUT,start_new_session=True)
    joints=subprocess.Popen([sys.executable,str(candidate/'scripts/diagnostics/record_joints.py'),
        str(out/'joints.jsonl'),str(out/'stop_recording')],stdout=(out/'joints.log').open('x'),
        stderr=subprocess.STDOUT,start_new_session=True)
    end=time.monotonic()+60
    while True:
        try:
            states=[json.loads(line) for line in (out/'worldstate/world_state.jsonl').read_text().splitlines()]
            joint_rows=[json.loads(line) for line in (out/'joints.jsonl').read_text().splitlines()]
            if sum(r['channel']=='topic' and not r['issues'] for r in states)>=2 and any('gripper_left_joint' in r['name'] for r in joint_rows):break
        except (FileNotFoundError,json.JSONDecodeError):pass
        if time.monotonic()>=end or recorder.poll() is not None or joints.poll() is not None:
            raise RuntimeError('required evidence unavailable; no task dispatched')
        time.sleep(.1)
    status['status']='TASK_RUNNING'
    driver=subprocess.Popen([sys.executable,str(candidate/'runtime/run_public_push_task.py'),
        str(out/'public_task.json'),str(out/'runtime'),'--backend',backend],
        stdout=(out/'runtime.log').open('x'),stderr=subprocess.STDOUT,start_new_session=True)
    driver.wait(timeout=float(public['execution_budget']['max_wall_s'])+60.)
    status['driver_exit']=driver.returncode
    returned=json.loads((out/'runtime/runtime_result.json').read_text())
    status.update(status='EXECUTED',runtime_status=returned['status'],agent_claimed_success=returned['agent_claimed_success'])
    time.sleep(2);final=truth('gt_after.json')
except Exception as exc:
    status.update(status='FAILED',error=type(exc).__name__+': '+str(exc))
    try:final=truth('gt_after_failure.json')
    except Exception as error:status['truth_error']=str(error)
finally:
    (out/'stop_recording').touch(exist_ok=True)
    for proc in (driver,recorder,joints,stack):stop(proc)
    (out/'run_status.json').write_text(json.dumps(status,indent=2))

if final is not None and (out/'joints.jsonl').exists():
    links=['open_manipulator_x::%s::%s_collision'%(name,name) for name in ['link5','gripper_left_link','gripper_right_link']]
    rest=next(o['initial_pose'][2] for o in spec['objects'] if o['name']==target)
    subprocess.run([sys.executable,str(original/'benchmark/evidence/recorder.py'),
        '--physics-log',str(out/'physics.jsonl'),'--contact-log',str(out/'contacts.jsonl'),
        '--joint-log',str(out/'joints.jsonl'),'--task',str(task),'--task-id',spec['task_id'],
        '--run-id','runtime-'+label,'--target',target,'--protected',*protected,
        '--rest-height',str(rest),'--pusher-links',*links,'--gripper-joint','gripper_left_joint',
        '--out',str(out/'evidence_bundle.json')],check=True,stdout=(out/'bundle_build.log').open('x'),stderr=subprocess.STDOUT)
    bundle=json.loads((out/'evidence_bundle.json').read_text());final['evidence']=bundle
    final['trajectory']={name:dict(max_z_m=max(s[5] for s in entry['samples'])) for name,entry in bundle['objects'].items() if entry['samples']}
    final.update(agent_claimed_success=status['agent_claimed_success'],agent_claim_source='public Runtime result')
    (out/'observation.json').write_text(json.dumps(final,indent=2))
    subprocess.run([sys.executable,str(original/'benchmark/evaluators/evaluate.py'),str(task),str(out/'observation.json')],
        check=True,stdout=(out/'verdict.json').open('x'),stderr=(out/'evaluator.stderr').open('x'))
print(json.dumps(status))
