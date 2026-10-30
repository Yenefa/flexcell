"""Validate raw Gazebo contact snapshots without inferring zero from missing data."""
from collections import Counter
import json
import math
from pathlib import Path
import statistics


def require(value, message):
    if not value:
        raise ValueError('contact evidence: ' + message)


def number(value):
    require(type(value) in (int, float) and math.isfinite(value), 'nonfinite or nonnumeric value')
    return value


def vector(value):
    require(isinstance(value, dict), 'invalid protobuf Vector3d')
    # Proto3 omits scalar zero fields, but the force MESSAGE must exist.
    return [number(value.get(axis, 0.)) for axis in ('x', 'y', 'z')]


def entity(value):
    require(type(value) is int or isinstance(value, str) and value.isdecimal(), 'invalid entity id')
    result = int(value)
    require(result > 0, 'missing entity id')
    return result


def observation(target):
    require(isinstance(target, dict), 'invalid watched target')
    require(type(target.get('component_present')) is bool, 'missing component availability')
    pose = target.get('pose')
    if pose is not None:
        require(isinstance(pose, list) and len(pose) == 7, 'invalid body pose')
        for value in pose: number(value)
        require(.999 <= math.sqrt(sum(x*x for x in pose[3:])) <= 1.001, 'invalid body quaternion')
    if not target['component_present']:
        require(target.get('contacts') is None, 'missing component has invented contact data')
        return dict(state='UNKNOWN', force_magnitude_n=None, contacts=None)
    require(pose is not None, 'component without body pose')
    own = entity(target.get('collision_entity'))
    proto = target.get('contacts')
    require(isinstance(proto, dict), 'missing raw contact protobuf')
    contacts = proto.get('contact', [])
    require(isinstance(contacts, list), 'invalid contact array')
    if not contacts:
        return dict(state='NO_REPORTED_CONTACTS', force_magnitude_n=None, contacts=0)
    force_vectors, complete = [], True
    for contact in contacts:
        require(isinstance(contact, dict), 'invalid contact')
        require(entity(contact.get('collision1', {}).get('id')) == own, 'contact belongs to another collision')
        require(entity(contact.get('collision2', {}).get('id')) != own, 'invalid self collision')
        points, wrenches = contact.get('position', []), contact.get('wrench', [])
        require(isinstance(points, list) and points and isinstance(wrenches, list), 'missing contact points')
        for point in points: vector(point)
        for normal in contact.get('normal', []): vector(normal)
        for depth in contact.get('depth', []): number(depth)
        complete = complete and len(points) == len(wrenches)
        for wrench in wrenches:
            require(isinstance(wrench, dict), 'invalid wrench')
            forces = []
            for body in ('body_1_wrench', 'body_2_wrench'):
                data = wrench.get(body, {})
                require(isinstance(data, dict), 'invalid body wrench')
                if 'torque' in data: vector(data['torque'])
                forces.append(vector(data['force']) if 'force' in data else None)
            if any(force is None for force in forces):
                complete = False
                continue
            require(math.dist(forces[0], [-x for x in forces[1]]) <= 1e-9,
                    'raw bilateral forces are not equal and opposite')
            force_vectors.append(forces[0])
    if not complete:
        return dict(state='CONTACTS_FORCE_UNKNOWN', force_magnitude_n=None, contacts=len(contacts))
    total = [math.fsum(v[axis] for v in force_vectors) for axis in range(3)]
    return dict(state='CONTACTS_WITH_FORCE', force_magnitude_n=math.hypot(*total), contacts=len(contacts),
                raw_body_1_force_sum_n=total,
                # body_1 is the collision this sensor belongs to, so these are the
                # forces applied TO the watched body by each contact partner.
                body_1_point_forces_n=[list(v) for v in force_vectors])


def verify_rows(rows, declaration):
    count, step = declaration['samples'], declaration['step_ns']
    require(len(rows) == count, 'sample count differs from declaration')
    require(rows[0]['sim_ns'] in (0, step), 'unexpected first physics tick')
    targets = declaration['targets']
    require(set(targets) == {'positive', 'empty', 'missing'}, 'invalid control declaration')
    expected = set(targets.values())
    states, settled, all_forces = {name: Counter() for name in expected}, [], 0
    previous, bindings = None, None
    for row in rows:
        require(type(row.get('schema_version')) is int and row['schema_version'] == 1 and
                row.get('source') == 'ECM_POST_PHYSICS', 'unknown raw schema or source')
        require(type(row.get('step_ns')) is int and row['step_ns'] == step and
                type(row.get('sim_ns')) is int and type(row.get('monotonic_ns')) is int and
                row['sim_ns'] >= 0 and row['monotonic_ns'] > 0, 'invalid physics clock')
        if previous is not None:
            require(row['sim_ns'] - previous['sim_ns'] == step and
                    row['monotonic_ns'] > previous['monotonic_ns'], 'missing or reordered physical step')
        previous = row
        require(set(row['targets']) == expected, 'missing or extra watched collision')
        observed = {name: observation(row['targets'][name]) for name in expected}
        for name, result in observed.items(): states[name][result['state']] += 1
        positive = observed[targets['positive']]
        require(positive['state'] != 'CONTACTS_FORCE_UNKNOWN', 'reported contact lacks force data')
        if positive['state'] == 'CONTACTS_WITH_FORCE': all_forces += 1
        if declaration['settle_from_ns'] <= row['sim_ns'] <= declaration['settle_to_ns']:
            require(positive['state'] != 'UNKNOWN', 'weight control component missing')
            settled.append(positive['force_magnitude_n'])
        if row['sim_ns'] >= declaration['availability_from_ns']:
            current = tuple(entity(row['targets'][targets[role]].get('collision_entity'))
                            for role in ('positive', 'empty', 'missing'))
            require(len(set(current)) == 3 and all(row['targets'][name].get('pose') is not None
                                                 for name in expected), 'control collision binding unavailable or aliased')
            if bindings is None: bindings = current
            require(current == bindings, 'control collision identity changed')
            require(observed[targets['empty']]['state'] == 'NO_REPORTED_CONTACTS',
                    'elevated static control is not an available empty contact set')
            require(observed[targets['missing']]['state'] == 'UNKNOWN', 'missing sensor was reported as observed')
    expected_settled = (declaration['settle_to_ns'] - declaration['settle_from_ns']) // step + 1
    require(len(settled) == expected_settled, 'settled window incomplete')
    forces = [f for f in settled if f is not None]
    require(len(forces) >= declaration['min_force_samples'], 'positive force coverage below declaration')
    mean = statistics.fmean(forces)
    require(declaration['force_mean_min_n'] <= mean <= declaration['force_mean_max_n'],
            'weight control magnitude differs from m*g')
    return dict(status='CONTACT_PIPELINE_PASS', samples=len(rows), physics_step_ns=step,
                first_sim_ns=rows[0]['sim_ns'], last_sim_ns=rows[-1]['sim_ns'],
                settled_samples=len(settled), settled_force_samples=len(forces),
                measured_force_samples=all_forces, mean_force_magnitude_n=mean,
                signed_target_force_calibrated=False,
                states={name: dict(counts) for name, counts in states.items()},
                logical_robot_tasks=0, default_admission='NO_GO',
                interpretation='Standalone sensor pipeline only; no integrated arm, attachment or contact-grasp qualification')


def verify_file(path, declaration):
    with Path(path).open() as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    return verify_rows(rows, declaration)
