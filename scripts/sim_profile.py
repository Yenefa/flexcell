#!/usr/bin/env python3
"""Materialize a new simulation profile; never rewrite a historical world."""
from copy import deepcopy
import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[1]
BACKENDS = ('teleport', 'velocity_servo', 'detachable_joint')


DECISION_POLICIES = ('fsm', 'jev', 'llm', 'hybrid')


# Opt-in scenes keep the shipped two-box world and every historical profile
# byte-compatible. A scene adds same-spec models and declares the object set;
# it does not generalize shape, size or perception.
SCENES = ('three_boxes', 'tagged_three_boxes')
THREE_OBJECTS = ('target_box_a', 'target_box_b', 'target_box_c')
TAGGED_CAMERA_POSE = [.30, -.30, .40, 0., .98, 2.09]


def add_visual_tags(world):
    """Attach upstream tag textures; the 25 mm black square has a white border."""
    tags = []
    for tag_id, name in enumerate(THREE_OBJECTS):
        link = world.find("model[@name='%s']/link[@name='link']" % name)
        visual = ET.SubElement(link, 'visual', name='apriltag_%d' % tag_id)
        ET.SubElement(visual, 'pose').text = '0 0 0.0177 0 0 0'
        plane = ET.SubElement(ET.SubElement(visual, 'geometry'), 'plane')
        ET.SubElement(plane, 'normal').text = '0 0 1'
        ET.SubElement(plane, 'size').text = '0.03125 0.03125'
        material = ET.SubElement(visual, 'material')
        ET.SubElement(material, 'ambient').text = '1 1 1 1'
        ET.SubElement(material, 'diffuse').text = '1 1 1 1'
        metal = ET.SubElement(ET.SubElement(material, 'pbr'), 'metal')
        asset = ROOT / 'worlds' / 'tags' / ('tag36_11_%05d_texture.png' % tag_id)
        if not asset.is_file():
            raise ValueError('missing upstream AprilTag image: ' + str(asset))
        ET.SubElement(metal, 'albedo_map').text = asset.resolve().as_uri()
        ET.SubElement(metal, 'metalness').text = '0'
        ET.SubElement(metal, 'roughness').text = '1'
        tags.append(dict(id=tag_id, object=name, frame='vision_tag_%d' % tag_id,
                         tag_to_center=[0., 0., -.0177, 0., 0., 0., 1.]))
    return tags


def profile(out, backend='velocity_servo', camera=False, skill_backend='legacy',
            joint_hold_sim_s=0., physics_step_s=None, *, contact_trace=False, release_clearance_m=None,
            qualification_no_recovery=False, synchronous_step_logs=False, resume_completed_objects=False,
            decision_policy='fsm', hybrid_threshold=None, scene=None, perception_only=False,
            level_release_tolerance_deg=None, zone_2_pose=None):
    if backend not in BACKENDS or skill_backend not in ('legacy', 'mtc'):
        raise ValueError('unsupported backend')
    if level_release_tolerance_deg is not None:
        if skill_backend != 'mtc' or backend != 'detachable_joint':
            raise ValueError('level release requires skill_backend=mtc and backend=detachable_joint')
        if (isinstance(level_release_tolerance_deg, bool)
                or not isinstance(level_release_tolerance_deg, (int, float))
                or not math.isfinite(level_release_tolerance_deg)
                or not 0. <= level_release_tolerance_deg <= 45.):
            raise ValueError('the level-release tolerance must be a finite number within [0, 45] deg')
    if scene is not None and scene not in SCENES:
        raise ValueError('unknown scene %r %r' % (scene, SCENES))
    tagged = scene == 'tagged_three_boxes'
    three_boxes = scene in ('three_boxes', 'tagged_three_boxes')
    if tagged and not camera:
        raise ValueError('the tagged scene requires camera=True')
    if perception_only and (not tagged or backend != 'detachable_joint' or contact_trace or joint_hold_sim_s):
        raise ValueError('perception_only requires the tagged detachable_joint scene without carry qualification')
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
    if three_boxes:
        config['observe_server']['ros__parameters']['tracked_objects'] = list(THREE_OBJECTS)
        config['observe_server']['ros__parameters']['object_target_box_c_size'] = [.035, .035, .035]
    # One declaration of the object set, propagated to every node that validates
    # names: a new same-spec box is then a configuration change only.
    tracked = list(config['observe_server']['ros__parameters']['tracked_objects'])
    for name, node in config.items():
        if 'ros__parameters' in node:
            node['ros__parameters']['log_dir'] = str(out / 'skills')
            if three_boxes and name != 'observe_server':
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
    if zone_2_pose is not None:
        pose = tuple(float(v) for v in zone_2_pose)
        if len(pose) != 3 or not all(math.isfinite(v) for v in pose):
            raise ValueError('zone_2_pose must be three finite numbers')
        params = config['task_fsm_server']['ros__parameters']
        params['zone_2_x'], params['zone_2_y'], params['zone_2_z'] = pose
    config['task_fsm_server']['ros__parameters']['decision_policy'] = decision_policy
    if decision_policy == 'hybrid':
        config['task_fsm_server']['ros__parameters']['hybrid_threshold'] = float(hybrid_threshold)
    if resume_completed_objects:
        config['task_fsm_server']['ros__parameters']['resume_completed_objects'] = True
    if qualification_no_recovery:
        config['task_fsm_server']['ros__parameters']['recovery_budget'] = 0
    config['task_fsm_server']['ros__parameters']['episode_dir'] = str(out / 'episodes')
    config['move_to_pose_server']['ros__parameters']['enable_mtc_handoff'] = skill_backend == 'mtc'
    if level_release_tolerance_deg is not None:
        # The shared profile is the single declaration used by normal launch
        # sessions and smoke runs. The planner target and measured release gate
        # must agree before any stack is started.
        tolerance = float(level_release_tolerance_deg)
        config.setdefault('mtc_planner', {}).setdefault('ros__parameters', {})[
            'level_release_pitch_tolerance_deg'] = tolerance
        config['place_server']['ros__parameters']['max_release_tilt_deg'] = tolerance
    base = 'flexcell_velocity_servo.sdf' if backend == 'velocity_servo' else 'flexcell_world.sdf'
    tree = ET.parse(ROOT / 'worlds' / base)
    world = tree.getroot().find('world')
    if three_boxes:
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
    if not perception_only:
        trace = ET.SubElement(world, 'plugin', name='flexcell::PhysicsTrace',
                              filename='libflexcell_physics_trace.so')
        if three_boxes:
            for name in tracked:
                ET.SubElement(trace, 'object').text = name
    if backend == 'detachable_joint' and not perception_only:
        guard = ET.SubElement(world, 'plugin', name='flexcell::DetachableCarryGuard',
                              filename='libflexcell_detachable_carry.so')
        if three_boxes:
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
        ET.SubElement(model, 'pose').text = (' '.join(map(str, TAGGED_CAMERA_POSE)) if tagged
                                           else '0.55 -0.45 0.55 0 0.693 2.297')
        link = ET.SubElement(model, 'link', name='camera_link')
        sensor = ET.SubElement(link, 'sensor', name='rgb', type='camera')
        ET.SubElement(sensor, 'always_on').text = 'true'
        ET.SubElement(sensor, 'update_rate').text = '2' if tagged else '10'
        ET.SubElement(sensor, 'topic').text = '/flexcell/camera/rgb'
        rgb = ET.SubElement(sensor, 'camera')
        ET.SubElement(rgb, 'horizontal_fov').text = '0.80' if tagged else '1.20'
        image = ET.SubElement(rgb, 'image')
        dimensions = ('1280', '960') if tagged else ('640', '480')
        for key, value in [('width', dimensions[0]), ('height', dimensions[1]), ('format', 'R8G8B8')]:
            ET.SubElement(image, key).text = value
        clip = ET.SubElement(rgb, 'clip')
        ET.SubElement(clip, 'near').text = '0.02'
        ET.SubElement(clip, 'far').text = '3.0'
    calibration = None
    if tagged:
        # Sensor/tag calibration only: no box world coordinates enter the reader.
        calibration = dict(camera_frame='dataset_camera/camera_link/rgb',
                           camera_sdf_pose=list(TAGGED_CAMERA_POSE),
                           tag_size_m=.025, tags=add_visual_tags(world))
        if perception_only:
            calibration['perception_only'] = True
    if synchronous_step_logs:
        for name in ('flexcell::PhysicsTrace', 'flexcell::ContactTrace'):
            ET.SubElement(world.find("plugin[@name='%s']" % name), 'flush_each_step').text = 'true'
    out.mkdir(parents=True, exist_ok=True)
    params_path, world_path = out / 'params.yaml', out / 'world.sdf'
    with params_path.open('x') as stream:
        yaml.safe_dump(config, stream, sort_keys=False)
    with world_path.open('xb') as stream:
        tree.write(stream, encoding='utf-8', xml_declaration=True)
    if tagged:
        with (out / 'vision.json').open('x') as stream:
            json.dump(calibration, stream, indent=2, allow_nan=False)
            stream.write('\n')
    return params_path, world_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='directory for a new profile')
    parser.add_argument('--backend', choices=BACKENDS, default='velocity_servo')
    parser.add_argument('--skill-backend', choices=('legacy', 'mtc'), default='legacy')
    parser.add_argument('--camera', action='store_true')
    parser.add_argument('--scene', choices=SCENES)
    parser.add_argument('--level-release-tolerance-deg', type=float,
                        help='enable level release with one planner/gate limit; requires mtc + detachable_joint')
    args = parser.parse_args(argv)
    try:
        params, world = profile(
            args.out, backend=args.backend, camera=args.camera, skill_backend=args.skill_backend,
            scene=args.scene, level_release_tolerance_deg=args.level_release_tolerance_deg)
    except (ValueError, FileExistsError) as exc:
        parser.error(str(exc))
    result = dict(params=str(params.resolve()), world=str(world.resolve()))
    if args.scene == 'tagged_three_boxes':
        result['vision'] = str((args.out / 'vision.json').resolve())
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
