#!/usr/bin/env python3
"""Materialize a new simulation profile; never rewrite a historical world."""
from copy import deepcopy
from pathlib import Path
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[1]
BACKENDS = ('teleport', 'velocity_servo', 'detachable_joint')


def profile(out, backend='velocity_servo', camera=False, skill_backend='legacy'):
    if backend not in BACKENDS or skill_backend not in ('legacy', 'mtc'):
        raise ValueError('unsupported backend')
    out = Path(out)
    config = yaml.safe_load((ROOT / 'src/flexcell/flexcell_skills/config/week1.yaml').read_text())
    config.update(yaml.safe_load((ROOT / 'src/flexcell/flexcell_skills/config/move_to_pose.yaml').read_text()))
    for node in config.values():
        if 'ros__parameters' in node:
            node['ros__parameters']['log_dir'] = str(out / 'skills')
    for name in ('pick_server', 'carry_server'):
        config[name]['ros__parameters']['carry_backend'] = backend
    for name in ('pick_server', 'place_server'):
        config[name]['ros__parameters']['skill_backend'] = skill_backend
        config[name]['ros__parameters']['record_execution_commands'] = bool(camera)
    config['task_fsm_server']['ros__parameters']['decision_policy'] = 'fsm'
    config['task_fsm_server']['ros__parameters']['episode_dir'] = str(out / 'episodes')
    config['move_to_pose_server']['ros__parameters']['enable_mtc_handoff'] = skill_backend == 'mtc'
    base = 'flexcell_velocity_servo.sdf' if backend == 'velocity_servo' else 'flexcell_world.sdf'
    tree = ET.parse(ROOT / 'worlds' / base)
    world = tree.getroot().find('world')
    ET.SubElement(world, 'plugin', name='flexcell::PhysicsTrace', filename='libflexcell_physics_trace.so')
    if backend == 'detachable_joint':
        ET.SubElement(world, 'plugin', name='flexcell::DetachableCarryGuard',
                      filename='libflexcell_detachable_carry.so')
    if camera:
        sensors = ET.SubElement(world, 'plugin', name='gz::sim::systems::Sensors',
                                filename='gz-sim-sensors-system')
        ET.SubElement(sensors, 'render_engine').text = 'ogre2'
        model = ET.SubElement(world, 'model', name='dataset_camera')
        ET.SubElement(model, 'static').text = 'true'
        ET.SubElement(model, 'pose').text = '0.55 -0.45 0.55 0 0.693 2.297'
        link = ET.SubElement(model, 'link', name='camera_link')
        sensor = ET.SubElement(link, 'sensor', name='rgb', type='camera')
        ET.SubElement(sensor, 'always_on').text = 'true'
        ET.SubElement(sensor, 'update_rate').text = '10'
        ET.SubElement(sensor, 'topic').text = '/flexcell/camera/rgb'
        rgb = ET.SubElement(sensor, 'camera')
        ET.SubElement(rgb, 'horizontal_fov').text = '1.20'
        image = ET.SubElement(rgb, 'image')
        for key, value in [('width', '640'), ('height', '480'), ('format', 'R8G8B8')]:
            ET.SubElement(image, key).text = value
        clip = ET.SubElement(rgb, 'clip')
        ET.SubElement(clip, 'near').text = '0.02'
        ET.SubElement(clip, 'far').text = '3.0'
    out.mkdir(parents=True, exist_ok=True)
    params_path, world_path = out / 'params.yaml', out / 'world.sdf'
    with params_path.open('x') as stream:
        yaml.safe_dump(config, stream, sort_keys=False)
    with world_path.open('xb') as stream:
        tree.write(stream, encoding='utf-8', xml_declaration=True)
    return params_path, world_path
