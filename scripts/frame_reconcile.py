#!/usr/bin/env python3
"""Reconcile live camera frames.jsonl against the recorder's lossless rosbag.

The live recorder subscribes with BEST_EFFORT; under CI contention a handful of
camera messages can be lost even though the rosbag (a separate subscriber) keeps
every source image. This module backfills those missing rows from the bag itself,
so the exported dataset has no sampling gaps, WITHOUT fabricating pixels: every
backfilled image and its aligned state/action come from the bag. Only the
window-mapping monotonic_ns is linearly interpolated between neighbouring real
frames (sim<->wall is linear at fixed RTF) and each backfilled row is labelled
backfilled_from_bag=true / monotonic_ns_source=interpolated.

Pure stdlib + sqlite3. Message deserialization and image encoding are injected so
this is testable without ROS; the recorder passes rclpy.serialize/write_png.
"""
import json
from pathlib import Path
import sqlite3


def _stamp_ns(header):
    return header.stamp.sec * 10 ** 9 + header.stamp.nanosec


def _causal(history, stamp, max_age_ns):
    chosen = None
    for entry in history:
        if entry['sim_ns'] <= stamp and (chosen is None or entry['sim_ns'] > chosen['sim_ns']):
            chosen = entry
    if chosen is None or stamp - chosen['sim_ns'] > max_age_ns:
        return None
    return chosen


def _find_dbs(bag_dir):
    dbs = sorted(Path(bag_dir).rglob('*.db3'))
    if not dbs:
        raise ValueError('no rosbag sqlite db under %s' % bag_dir)
    return dbs


def _read_messages(dbs, name, require):
    """Return all serialized messages for a topic across every split db file."""
    found = False
    out = []
    for db in dbs:
        conn = sqlite3.connect(str(db))
        try:
            row = conn.execute('SELECT id FROM topics WHERE name=?', (name,)).fetchone()
            if row is not None:
                found = True
                out.extend(data for (data,) in conn.execute(
                    'SELECT data FROM messages WHERE topic_id=? ORDER BY timestamp', (row[0],)))
        finally:
            conn.close()
    if require and not found:
        raise ValueError('bag missing required topic: %s' % name)
    return out


def _interp(anchors, stamp):
    """Linear interpolation of monotonic_ns at a sim stamp from real anchors."""
    if not anchors:
        return None
    lo = hi = None
    for sim, mono in anchors:
        if sim <= stamp:
            lo = (sim, mono)
        elif hi is None:
            hi = (sim, mono)
            break
    if lo and hi and hi[0] != lo[0]:
        frac = (stamp - lo[0]) / (hi[0] - lo[0])
        return int(round(lo[1] + frac * (hi[1] - lo[1])))
    if lo:
        return lo[1]
    return hi[1]


def reconcile_run(out, bag_dir, *, deserialize, write_png, joints,
                  camera_topic='/flexcell/camera/rgb', state_topic='/joint_states',
                  reference_topic='/arm_controller/controller_state',
                  command_topic='/flexcell/execution_command',
                  state_age_ns=50_000_000, gripper_age_ns=600_000_000_000):
    out = Path(out)
    frames_path = out / 'frames.jsonl'
    rows = [json.loads(line) for line in frames_path.read_text().splitlines() if line.strip()]
    existing = {row['sim_ns'] for row in rows}

    dbs = _find_dbs(bag_dir)
    camera = []
    for data in _read_messages(dbs, camera_topic, True):
        msg = deserialize(camera_topic, data)
        camera.append((_stamp_ns(msg.header), msg))
    states = []
    for data in _read_messages(dbs, state_topic, True):
        msg = deserialize(state_topic, data)
        states.append({'sim_ns': _stamp_ns(msg.header),
                       'positions': dict(zip(msg.name, msg.position))})
    references = []
    for data in _read_messages(dbs, reference_topic, True):
        msg = deserialize(reference_topic, data)
        references.append({'sim_ns': _stamp_ns(msg.header),
                           'positions': dict(zip(msg.joint_names, msg.reference.positions))})
    grippers = []
    for data in _read_messages(dbs, command_topic, False):
        raw = deserialize(command_topic, data)
        try:
            payload = json.loads(raw.data)
        except (ValueError, TypeError):
            continue
        if payload.get('kind') == 'gripper_position_target' and payload.get('accepted') is True and 'sim_ns' in payload:
            grippers.append(payload)

    cam_map = {}
    for stamp, msg in camera:
        cam_map.setdefault(stamp, msg)
    expected = sorted(cam_map)
    missing = [stamp for stamp in expected if stamp not in existing]
    if not missing:
        return dict(status='COMPLETE', expected=len(expected), existing=len(existing),
                    frames_total=len(rows),
                    valid_total=sum(1 for row in rows if row.get('valid') is True),
                    backfilled=0, backfilled_stamps=[])

    anchors = sorted((row['sim_ns'], row['monotonic_ns'])
                     for row in rows if row.get('monotonic_ns') is not None)
    next_index = max((row['frame_index'] for row in rows if isinstance(row.get('frame_index'), int)),
                     default=-1) + 1
    backfilled, errors = [], []
    for stamp in missing:
        msg = cam_map[stamp]
        rel = 'images/backfill_%09d.png' % next_index
        try:
            write_png(out / rel, msg)
        except Exception as exc:
            errors.append('backfill_image_failed %d: %s' % (stamp, exc))
            continue
        row = dict(frame_index=next_index, sim_ns=stamp, monotonic_ns=_interp(anchors, stamp),
                   monotonic_ns_source='interpolated', image=rel, valid=False, reasons=[],
                   backfilled_from_bag=True)
        next_index += 1
        state = _causal(states, stamp, state_age_ns)
        reference = _causal(references, stamp, state_age_ns)
        gripper = _causal(grippers, stamp, gripper_age_ns)
        for name, value in [('state', state), ('controller_reference', reference), ('gripper_target', gripper)]:
            row[name] = value
            if value is None:
                row['reasons'].append('missing_or_stale_' + name)
        if state is not None and reference is not None and gripper is not None:
            try:
                row['observation.state'] = [state['positions'].get(n) for n in joints]
                row['action'] = [reference['positions'].get(n) for n in joints[:4]] + [gripper['position']]
                if any(v is None or not isinstance(v, (int, float)) for v in
                       row['observation.state'] + row['action']):
                    row['reasons'].append('incomplete_or_nonfinite_joints')
            except (KeyError, TypeError) as exc:
                row['reasons'].append('align_error: ' + str(exc))
        row['valid'] = not row['reasons']
        backfilled.append(row)

    merged = sorted(rows + backfilled, key=lambda row: row['sim_ns'])
    tmp = frames_path.with_suffix('.jsonl.reconciled')
    tmp.write_text(''.join(json.dumps(row, allow_nan=False) + chr(10) for row in merged))
    tmp.replace(frames_path)
    return dict(status='RECONCILED', expected=len(expected), existing=len(existing),
                frames_total=len(merged),
                valid_total=sum(1 for row in merged if row.get('valid') is True),
                backfilled=len(backfilled),
                backfilled_stamps=[row['sim_ns'] for row in backfilled],
                backfilled_invalid=sum(1 for row in backfilled if not row['valid']),
                errors=errors)
