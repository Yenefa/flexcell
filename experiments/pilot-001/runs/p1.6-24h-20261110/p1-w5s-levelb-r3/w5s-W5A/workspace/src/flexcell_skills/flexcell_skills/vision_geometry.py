"""Read-only camera/tag geometry. No simulator state or actuator interfaces."""
import math

from flexcell_skills.joint_follow import _multiply, _pose


def compose(parent, child):
    p, q = _pose(parent)
    c, r = _pose(child)
    rotated = _multiply(_multiply(q, c + [0.]), [-q[0], -q[1], -q[2], q[3]])
    return [p[i] + rotated[i] for i in range(3)] + _multiply(q, r)


def optical_pose(camera_sdf_pose):
    """Gazebo camera: X forward, Y left, Z up; optical: Z forward, X right, Y down."""
    if len(camera_sdf_pose) != 6 or not all(math.isfinite(v) for v in camera_sdf_pose):
        raise ValueError('camera extrinsic must contain six finite values')
    x, y, z, roll, pitch, yaw = camera_sdf_pose
    cr, cp, cy = [math.cos(v / 2) for v in (roll, pitch, yaw)]
    sr, sp, sy = [math.sin(v / 2) for v in (roll, pitch, yaw)]
    q = [sr*cp*cy-cr*sp*sy, cr*sp*cy+sr*cp*sy,
         cr*cp*sy-sr*sp*cy, cr*cp*cy+sr*sp*sy]
    return compose([x, y, z] + q, [0., 0., 0., -.5, .5, -.5, .5])


def validate_calibration(calibration):
    optical_pose(calibration['camera_sdf_pose'])
    size = calibration['tag_size_m']
    if not math.isfinite(size) or size <= 0 or not calibration['camera_frame']:
        raise ValueError('camera frame and positive tag size are required')
    tags = calibration['tags']
    if not tags:
        raise ValueError('at least one tag is required')
    for key in ('id', 'object', 'frame'):
        values = [tag[key] for tag in tags]
        if len(set(values)) != len(values):
            raise ValueError('duplicate tag ' + key)
    for tag in tags:
        if (type(tag['id']) is not int or tag['id'] < 0
                or not tag['object'] or not tag['frame']):
            raise ValueError('invalid tag identity')
        _pose(tag['tag_to_center'])


def observations(calibration, image, info, detections, transforms):
    """Resolve one declared image frame; unmatched/old TF never supplies a pose.

    Inputs are small message views, not truth data. The caller supplies only
    transforms published for this image stamp by the upstream detector.
    """
    validate_calibration(calibration)
    stamp, frame = image['stamp_ns'], image['frame_id']
    error = image.get('error', '')
    if stamp <= 0 or frame != calibration['camera_frame']:
        error = error or 'invalid_image_header'
    if info is None or info['stamp_ns'] != stamp or info['frame_id'] != frame:
        error = error or 'camera_info_unmatched'
    elif (info['width'], info['height']) != (image['width'], image['height']):
        error = error or 'camera_info_size_mismatch'
    else:
        p, distortion = info['p'], info['d']
        if (len(p) != 12 or not all(math.isfinite(v) for v in p + distortion)
                or p[0] <= 0 or p[5] <= 0):
            error = error or 'camera_uncalibrated'
        elif any(abs(v) > 1e-9 for v in distortion):
            error = error or 'image_requires_rectification'
    if (detections is None or detections['stamp_ns'] != stamp
            or detections['frame_id'] != frame):
        error = error or 'detections_unmatched'
    result = {}
    world_camera = optical_pose(calibration['camera_sdf_pose'])
    for tag in calibration['tags']:
        reason, estimate = error, None
        found = ([] if detections is None else
                 [d for d in detections['tags'] if d['id'] == tag['id']])
        tf = transforms.get(tag['frame'])
        if not reason:
            if len(found) != 1:
                reason = 'tag_missing' if not found else 'tag_ambiguous'
            elif (found[0]['hamming'] != 0 or not math.isfinite(found[0]['margin'])
                  or found[0]['margin'] <= 0):
                reason = 'tag_quality_invalid'
            elif tf is None or tf['stamp_ns'] != stamp or tf['frame_id'] != frame:
                reason = 'tag_transform_unmatched'
            else:
                try:
                    estimate = compose(compose(world_camera, tf['pose']), tag['tag_to_center'])
                except (TypeError, ValueError) as exc:
                    reason = 'tag_transform_invalid: ' + str(exc)
        row = {'available': not bool(reason), 'reason': reason}
        if estimate is not None:
            row['world_center_m'] = estimate[:3]
        result[tag['object']] = row
    return {'source': 'VISION_APRILTAG', 'image_stamp_ns': stamp,
            'camera_frame': frame, 'objects': result}
