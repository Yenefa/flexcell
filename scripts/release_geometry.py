"""Read-only vector decomposition of a single recorded rigid carry/release.

This is a diagnostic, not an admission gate or a controller. Component vectors
add; their norms generally do not. The caller must bind the inputs to raw data.
"""
import math
import struct


def _require(condition, message):
    if not condition:
        raise ValueError('release geometry: ' + message)


def _vector(value, length):
    _require(isinstance(value, (list, tuple)) and len(value) == length,
             'wrong vector length')
    _require(all(type(x) in (int, float) and math.isfinite(x) for x in value),
             'nonnumeric or nonfinite vector')
    return list(value)


def _pose(value):
    value = _vector(value, 7)
    norm = math.sqrt(math.fsum(x*x for x in value[3:]))
    _require(.999 <= norm <= 1.001, 'invalid quaternion norm')
    return value[:3], [x/norm for x in value[3:]]


def _rotate(q, vector):
    # Rodrigues form for a unit quaternion, independent of the online code.
    u, w = q[:3], q[3]
    dot = math.fsum(a*b for a, b in zip(u, vector))
    cross = [u[1]*vector[2]-u[2]*vector[1],
             u[2]*vector[0]-u[0]*vector[2], u[0]*vector[1]-u[1]*vector[0]]
    return [2*dot*u[i] + (2*w*w-1)*vector[i] + 2*w*cross[i] for i in range(3)]


def _add(a, b):
    return [x+y for x, y in zip(a, b)]


def _sub(a, b):
    return [x-y for x, y in zip(a, b)]


def _measurement(vector):
    return dict(xyz_m=vector, norm_m=math.hypot(*vector), horizontal_m=math.hypot(*vector[:2]))


def decompose(*, parent, box, parent_box_reference, parent_ee,
              ee_target, box_goal, clearance_m, settled):
    """Separate same-step tracking, rigid geometry, residual and later motion.

    parent/box are simultaneous world poses at the last attached physics step.
    parent_box_reference is an earlier measured parent->box transform, never
    estimated from the release pose. parent_ee is a recorded fixed transform.
    The final reference is the actual task goal; clearance is included explicitly.
    """
    position, orientation = _pose(parent)
    body, _ = _pose(box)
    reference, _ = _pose(parent_box_reference)
    ee_translation, _ = _pose(parent_ee)
    ee_target, box_goal, settled = (_vector(x, 3) for x in (ee_target, box_goal, settled))
    _require(type(clearance_m) in (int, float) and math.isfinite(clearance_m) and clearance_m >= 0,
             'invalid clearance')
    clearance = [0., 0., clearance_m]
    box_target = _add(box_goal, clearance)
    ee = _add(position, _rotate(orientation, ee_translation))
    rigid_offset = _rotate(orientation, _sub(reference, ee_translation))
    predicted_box = _add(ee, rigid_offset)
    nominal_offset = _sub(box_target, ee_target)
    components = dict(
        ee_tracking=_sub(ee, ee_target),
        rigid_geometry=_sub(rigid_offset, nominal_offset),
        rigid_residual=_sub(body, predicted_box),
        release_to_settled=_sub(settled, body),
        clearance=clearance)
    total = [math.fsum(v[i] for v in components.values()) for i in range(3)]
    final = _sub(settled, box_goal)
    return dict(ee_at_release=ee, box_at_release=body, box_predicted_from_reference=predicted_box,
                actual_world_offset=rigid_offset, nominal_world_offset=nominal_offset,
                components={name: _measurement(v) for name, v in components.items()},
                release_error_to_clearance_target=_measurement(_sub(body, box_target)),
                release_error_to_goal=_measurement(_sub(body, box_goal)),
                final_error=_measurement(final), component_sum_xyz_m=total,
                closure_residual_m=math.dist(total, final),
                interpretation='Vector accounting for this recorded session; not causal population effects, '
                               'a success rate, or a changed qualification verdict')


def attachment_interval(physics, object_id, task_start_mono_ns, task_end_mono_ns):
    """Find one bounded task session without imposing the old 50 Hz tail claim.

    Returns the actual adjacent 2 ms edge records. It does not mark a sampled
    monitor or an existing gate as passed when their temporal coverage failed.
    """
    _require(type(task_start_mono_ns) is int and type(task_end_mono_ns) is int and
             0 < task_start_mono_ns < task_end_mono_ns, 'invalid task bounds')
    _require(len(physics) >= 3, 'incomplete physics stream')
    for i, row in enumerate(physics):
        _require(type(row.get('sim_ns')) is int and type(row.get('monotonic_ns')) is int,
                 'invalid clock')
        _require(row.get('step_ns') == 2_000_000 or i == 0 and row.get('step_ns') == 0,
                 'physics step changed')
        if i:
            previous = physics[i-1]
            _require(row['sim_ns'] - previous['sim_ns'] == 2_000_000 and
                     row['monotonic_ns'] > previous['monotonic_ns'], 'missing or unordered physics step')
    _require(physics[0]['monotonic_ns'] <= task_start_mono_ns and
             physics[-1]['monotonic_ns'] >= task_end_mono_ns, 'physics does not cover the task')
    task = [row for row in physics if task_start_mono_ns <= row['monotonic_ns'] <= task_end_mono_ns]
    _require(len(task) >= 3, 'incomplete task stream')
    states = []
    for row in task:
        obj = row.get('objects', {}).get(object_id, {})
        _require(type(obj.get('joint_component')) is bool, 'attachment state unavailable')
        _pose(row.get('parent_pose'))
        _pose(obj.get('pose'))
        states.append(obj['joint_component'])
    _require(states[0] is False and states[-1] is False, 'unbounded task attachment')
    starts = [i for i in range(1, len(states)) if states[i] and not states[i-1]]
    ends = [i for i in range(1, len(states)) if not states[i] and states[i-1]]
    _require(len(starts) == len(ends) == 1 and starts[0] < ends[0],
             'missing or ambiguous task attachment')
    first, end = starts[0], ends[0]
    return dict(before_bind=task[first-1], first_attached=task[first],
                last_attached=task[end-1], first_detached=task[end],
                last_task_step=task[-1], attached_steps=end-first,
                total_steps=len(physics), task_steps=len(task))


def decode_tf_static(data):
    """Decode the recorded little-endian CDR1 TFMessage without ROS libraries.

    Deliberately supports only this capsule's encoding. The original message is
    also independently decoded with rclpy and matched field-for-field in tests.
    """
    _require(isinstance(data, bytes) and data[:4] == b'\x00\x01\x00\x00',
             'unsupported CDR encoding')
    offset = 4

    def read(fmt, alignment):
        nonlocal offset
        offset += (-(offset-4)) % alignment
        value = struct.unpack_from('<' + fmt, data, offset)
        offset += struct.calcsize('<' + fmt)
        return value

    def string():
        nonlocal offset
        size, = read('I', 4)
        _require(1 < size <= 1024 and offset+size <= len(data), 'invalid CDR frame string')
        value = data[offset:offset+size]
        offset += size
        _require(value[-1:] == b'\0' and b'\0' not in value[:-1], 'invalid CDR string terminator')
        return value[:-1].decode('utf-8')

    try:
        count, = read('I', 4)
        _require(0 < count <= 1000, 'invalid CDR transform count')
        result = []
        for _ in range(count):
            seconds, nanoseconds = read('iI', 4)
            _require(0 <= nanoseconds < 10**9, 'invalid CDR timestamp')
            parent, child = string(), string()
            pose = list(read('7d', 8))
            _pose(pose)
            result.append(dict(parent=parent, child=child, stamp_ns=seconds*10**9+nanoseconds, pose=pose))
        _require(offset == len(data), 'unexpected trailing CDR data')
        _require(len({t['child'] for t in result}) == count, 'ambiguous static transform child')
        return result
    except (struct.error, UnicodeError) as error:
        raise ValueError('release geometry: malformed CDR') from error
