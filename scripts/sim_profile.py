#!/usr/bin/env python3
"""Materialize a new simulation profile; never rewrite a historical world."""
from copy import deepcopy
from pathlib import Path
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[1]
BACKENDS = ('teleport', 'velocity_servo', 'detachable_joint')


DECISION_POLICIES = ('fsm', 'jev', 'llm', 'hybrid')


# Opt-in scenes keep the shipped two-box world and every historical profile
# byte-compatible. A scene adds same-spec models and declares the object set;
# it does not generalize shape, size or perception.
SCENES = ('three_boxes',)
THREE_OBJECTS = ('target_box_a', 'target_box_b', 'target_box_c')


def profile(out, backend='velocity_servo', camera=False, skill_backend='legacy',
            joint_hold_sim_s=0., physics_step_s=None, *, contact_trace=False, release_clearance_m=None,
            qualification_no_recovery=False, synchronous_step_logs=False, resume_completed_objects=False,
            decision_policy='fsm', hybrid_threshold=None, scene=None):
    if backend not in BACKENDS or skill_backend not in ('legacy', 'mtc'):
        raise ValueError('unsupported backend')
    if scene is not None and scene not in SCENES:
        raise ValueError('unknown scene %r %r' % (scene, SCENES))
    if decision_policy not in DECISION_POLICIES:
        raise ValueError('unknown decision policy %r %r' % (decision_policy, DECISION_POLICIES))
    if decision_policy == 'hybrid':
        if not isinstance(hybrid_threshold, float) or not 0. < hybrid_threshold <= 1.:
            raise ValueError('the hybrid policy requires a declared threshold in (0, 1]')
    elif hybrid_threshold is not None:
        raise ValueError('the hybrid threshold belongs to the hybrid policy only')
    if contact_trace and (backend != 'detachable_joint' or physics_step_s != .002):
        raise ValueError('integrated contact trace requires the declared 2 ms joint profile')
    if release_clearance_m is not None and (not contact_trace or release_clearance_m != .05):
        raise ValueError('only the explicitly declared 50 mm release fixture is supported')
    if qualification_no_recovery and not contact_trace:
        raise ValueError('no-recovery qualification requires the declared contact profile')
    if synchronous_step_logs and not contact_trace:
        raise ValueError('synchronous step logs require the declared contact profile')
    out = Path(out)
    config = yaml.safe_load((ROOT / 'src/flexcell/flexcell_skills/config/week1.yaml').read_text())
    config.update(yaml.safe_load((ROOT / 'src/flexcell/flexcell_skills/config/move_to_pose.yaml').read_text()))
    if scene == 'three_boxes':
        config['observe_server']['ros__parameters']['tracked_objects'] = list(THREE_OBJECTS)
        config['observe_server']['ros__parameters']['object_target_box_c_size'] = [.035, .035, .035]
    # One declaration of the object set, propagated to every node that validates
    # names: a new same-spec box is then a configuration change only.
    tracked = list(config['observe_server']['ros__parameters']['tracked_objects'])
    for name, node in config.items():
        if 'ros__parameters' in node:
            node['ros__parameters']['log_dir'] = str(out / 'skills')
            if scene == 'three_boxes' and name != 'observe_server':
                node['ros__parameters']['tracked_objects'] = list(tracked)  # fresh copy: PyYAML must not emit aliases
    for name in ('pick_server', 'place_server', 'carry_server'):
        config[name]['ros__parameters']['carry_backend'] = backend
    if release_clearance_m is not None:
        config['place_server']['ros__parameters']['release_clearance_m'] = release_clearance_m
    if joint_hold_sim_s:
        if backend != 'detachable_joint' or not 0. < joint_hold_sim_s <= 20.:
            raise ValueError('joint simulation hold is only available for joint qualification')
        config['pick_server']['ros__parameters']['joint_follow_hold_sim_s'] = float(joint_hold_sim_s)
    for name in ('pick_server', 'place_server'):
        config[name]['ros__parameters']['skill_backend'] = skill_backend
        config[name]['ros__parameters']['record_execution_commands'] = bool(camera)
    config['task_fsm_server']['ros__parameters']['decision_policy'] = decision_policy
    if decision_policy == 'hybrid':
        config['task_fsm_server']['ros__parameters']['hybrid_threshold'] = float(hybrid_threshold)
    if resume_completed_objects:
        config['task_fsm_server']['ros__parameters']['resume_completed_objects'] = True
    if qualification_no_recovery:
        config['task_fsm_server']['ros__parameters']['recovery_budget'] = 0
    config['task_fsm_server']['ros__parameters']['episode_dir'] = str(out / 'episodes')
    config['move_to_pose_server']['ros__parameters']['enable_mtc_handoff'] = skill_backend == 'mtc'
    base = 'flexcell_velocity_servo.sdf' if backend == 'velocity_servo' else 'flexcell_world.sdf'
    tree = ET.parse(ROOT / 'worlds' / base)
    world = tree.getroot().find('world')
    if scene == 'three_boxes':
        model = ET.parse(ROOT / 'worlds' / 'target_box_c.sdf').getroot().find('model')
        if model is None or model.get('name') != 'target_box_c':
            raise ValueError('the three-box scene asset is missing target_box_c')
        world.append(model)
        if backend == 'velocity_servo':
            carry = world.find("plugin[@name='flexcell::CarryDynamics']")
            for item in list(carry.findall('allowed_model')):
                carry.remove(item)
            for name in tracked:
                ET.SubElement(carry, 'allowed_model').text = name
    if physics_step_s is not None:
        if backend != 'detachable_joint' or physics_step_s != .002:
            raise ValueError('only the declared 2 ms joint qualification step is supported')
        world.find('physics/max_step_size').text = '0.002'
    trace = ET.SubElement(world, 'plugin', name='flexcell::PhysicsTrace',
                          filename='libflexcell_physics_trace.so')
    if scene == 'three_boxes':
        for name in tracked:
            ET.SubElement(trace, 'object').text = name
    if backend == 'detachable_joint':
        guard = ET.SubElement(world, 'plugin', name='flexcell::DetachableCarryGuard',
                              filename='libflexcell_detachable_carry.so')
        if scene == 'three_boxes':
            for name in tracked:
                ET.SubElement(guard, 'allowed_model').text = name
    if contact_trace:
        physics = world.find("plugin[@name='gz::sim::systems::Physics']")
        ET.SubElement(physics, 'contacts_entity_names').text = 'true'
        observer = ET.SubElement(world, 'plugin', name='flexcell::ContactTrace', filename='libflexcell_contact_trace.so')
        watches = [(name, 'col') for name in tracked] + [('ground_plane', 'collision')]
        for name, collision in watches:
            watch = ET.SubElement(observer, 'watch')
            for key, value in [('model', name), ('link', 'link'), ('collision', collision)]:
                ET.SubElement(watch, key).text = value
            if name.startswith('target_box_'):
                link = world.find("model[@name='%s']/link[@name='link']" % name)
                sensor = ET.SubElement(link, 'sensor', name='qualification_contacts', type='contact')
                ET.SubElement(sensor, 'always_on').text = 'true'
                ET.SubElement(sensor, 'update_rate').text = '500'
                ET.SubElement(ET.SubElement(sensor, 'contact'), 'collision').text = collision
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
    if synchronous_step_logs:
        for name in ('flexcell::PhysicsTrace', 'flexcell::ContactTrace'):
            ET.SubElement(world.find("plugin[@name='%s']" % name), 'flush_each_step').text = 'true'
    out.mkdir(parents=True, exist_ok=True)
    params_path, world_path = out / 'params.yaml', out / 'world.sdf'
    with params_path.open('x') as stream:
        yaml.safe_dump(config, stream, sort_keys=False)
    with world_path.open('xb') as stream:
        tree.write(stream, encoding='utf-8', xml_declaration=True)
    return params_path, world_path
