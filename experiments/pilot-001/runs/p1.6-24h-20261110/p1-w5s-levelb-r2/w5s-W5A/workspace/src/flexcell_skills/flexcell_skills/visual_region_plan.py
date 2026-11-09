"""Plan table-top clearing from a recorded visual snapshot; no actuator I/O."""
import math

from flexcell_skills.vision_geometry import validate_calibration

BOX_SIDE_M = .035
BOX_RADIUS_M = math.sqrt(3.) * BOX_SIDE_M / 2.
BOX_INNER_RADIUS_M = BOX_SIDE_M / 2.
BOX_CENTER_Z_M = BOX_SIDE_M / 2.


def vector(value, length, label):
    if (not isinstance(value, (list, tuple)) or len(value) != length
            or any(isinstance(v, bool) or not isinstance(v, (int, float))
                   or not math.isfinite(v) for v in value)):
        raise ValueError(label + ' must contain %d finite numbers' % length)
    return tuple(float(v) for v in value)


def rectangle_distance(point, region):
    xmin, xmax, ymin, ymax = region
    return math.hypot(max(xmin - point[0], 0., point[0] - xmax),
                      max(ymin - point[1], 0., point[1] - ymax))


def snapshot_positions(capture, calibration, margin):
    """Use the first recorded frame, refusing incomplete or moving captures.

    Every declared frame is checked; later good frames never replace an invalid
    first observation. The record is a snapshot, not a claim of current pose.
    """
    if not isinstance(capture, dict) or not isinstance(calibration, dict):
        raise ValueError('capture and calibration must be objects')
    try:
        validate_calibration(calibration)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError('invalid visual calibration: ' + str(exc)) from exc
    names = {tag['object'] for tag in calibration['tags']}
    if not 1 <= len(names) <= 3 or not all(isinstance(n, str) and n.strip() for n in names):
        raise ValueError('this task supports one to three declared 35 mm boxes')
    frames = capture.get('frames')
    count = capture.get('requested_frames')
    if (capture.get('source') != 'VISION_APRILTAG' or capture.get('mode') != 'READ_ONLY'
            or capture.get('status') != 'OBSERVATIONS_AVAILABLE'
            or capture.get('capture_started') is not True
            or type(count) is not int or not 1 <= count <= 20
            or not isinstance(frames, list) or len(frames) != count
            or type(capture.get('captured_frames')) is not int
            or capture['captured_frames'] != count):
        raise ValueError('a complete AprilTag capture is required')
    first, last_stamp = None, 0
    for frame in frames:
        if not isinstance(frame, dict):
            raise ValueError('each visual frame must be an object')
        stamp = frame.get('image_stamp_ns')
        if (frame.get('source') != 'VISION_APRILTAG'
                or frame.get('camera_frame') != calibration['camera_frame']
                or type(stamp) is not int or stamp <= last_stamp):
            raise ValueError('visual frames must have matching camera identity and increasing stamps')
        last_stamp = stamp
        age = frame.get('image_age_at_receive_s')
        if (isinstance(age, bool) or not isinstance(age, (int, float))
                or not math.isfinite(age) or not -.05 <= age <= 1.):
            raise ValueError('image was stale or unsynchronised at capture')
        objects = frame.get('objects')
        if not isinstance(objects, dict) or set(objects) != names:
            raise ValueError('every calibrated object must appear exactly once')
        positions = {}
        for name in sorted(names):
            obj = objects[name]
            if not isinstance(obj, dict) or obj.get('available') is not True or obj.get('reason') != '':
                raise ValueError('visual object unavailable or ambiguous: ' + name)
            point = vector(obj.get('world_center_m'), 3, 'visual centre for ' + name)
            if abs(point[2] - BOX_CENTER_Z_M) > margin:
                raise ValueError('visual box is not at the declared table height: ' + name)
            positions[name] = point
        if first is None:
            first = positions
        elif any(math.dist(first[name], positions[name]) > margin for name in names):
            raise ValueError('scene moved during the visual capture')
    return first


def plan_region(capture, calibration, region, staging, position_margin_m=.010):
    """Select by visual footprint, clear all selected boxes, then restore them.

    Staging candidates are supplied by the caller. A bounded search avoids a
    greedy choice blocking the remaining boxes. It checks endpoint footprints,
    not arm reachability or paths; existing live Observe/MoveIt checks remain
    required. Restore targets use visual XY and the known fixture height.
    """
    region = vector(region, 4, 'region')
    if region[0] >= region[1] or region[2] >= region[3]:
        raise ValueError('region requires xmin < xmax and ymin < ymax')
    margin = vector([position_margin_m], 1, 'position margin')[0]
    if not 0. <= margin < BOX_INNER_RADIUS_M:
        raise ValueError('position margin must be nonnegative and below the box half-side')
    if not isinstance(staging, (list, tuple)) or len(staging) > 16:
        raise ValueError('at most sixteen staging candidates are supported')
    candidates = list(dict.fromkeys(vector(p, 2, 'staging point') for p in staging))
    positions = snapshot_positions(capture, calibration, margin)
    selected = []
    for name, point in positions.items():
        distance = rectangle_distance(point, region)
        # The capture records centres, not box attitude. The inscribed sphere
        # proves intersection; the circumscribed sphere proves separation.
        # Between those bounds, moving an actually outside box would violate
        # the request to leave outside objects alone, so refuse the ambiguity.
        if distance < BOX_INNER_RADIUS_M - margin:
            selected.append(name)
        elif distance <= BOX_RADIUS_M + margin:
            raise ValueError('region membership is ambiguous within the position margin: ' + name)
    clearance = 2. * (BOX_RADIUS_M + margin)
    candidates = [p for p in candidates if rectangle_distance(p, region) > BOX_RADIUS_M + margin]
    initial = {name: (p[0], p[1], BOX_CENTER_Z_M) for name, p in positions.items()}

    def free(state, moving, target):
        return all(math.dist(target[:2], p[:2]) > clearance
                   for name, p in state.items() if name != moving)

    def restore(state, clears):
        state = dict(state)
        for name, _ in reversed(clears):
            if not free(state, name, initial[name]):
                return False
            state[name] = initial[name]
        return True

    def search(state, remaining, clears):
        if not remaining:
            return clears if restore(state, clears) else None
        for name in remaining:
            for point in candidates:
                target = (*point, BOX_CENTER_Z_M)
                if free(state, name, target):
                    after = dict(state, **{name: target})
                    result = search(after, [n for n in remaining if n != name], clears + [(name, target)])
                    if result is not None:
                        return result
        return None

    clears = search(initial, selected, [])
    if clears is None:
        raise ValueError('no clear-and-restore sequence fits the declared staging candidates')
    moves = []
    for phase, entries in [('clear', clears),
                           ('restore', [(name, initial[name]) for name, _ in reversed(clears)])]:
        for name, target in entries:
            moves.append(dict(phase=phase, object_name=name, target_world_m=list(target)))
    first = capture['frames'][0]
    return dict(schema_version=1, status='PLANNED', source='VISION_APRILTAG',
                execution_ready=False, motion_dispatched=False,
                image_stamp_ns=first['image_stamp_ns'], image=first.get('image'),
                camera_frame=first['camera_frame'], region_xy_m=list(region),
                box_size_m=[BOX_SIDE_M] * 3, position_margin_m=margin,
                initial_visual_centres_m={n: list(p) for n, p in positions.items()},
                selected_objects=selected,
                untouched_objects=sorted(set(positions) - set(selected)),
                clear_complete_after=len(clears), moves=moves,
                requires_live_observe=True)
