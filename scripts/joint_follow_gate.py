"""Read-only per-trial gate for a declared joint-follow functional window."""
import json
import math
from pathlib import Path

from flexcell_skills.joint_follow import relative_pose


def _require(condition, detail):
    if not condition:
        raise ValueError('joint follow evidence: ' + detail)


def _rows(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def verify_run(run, object_id, *, min_duration_s=0., physics_step_ns=None, require_camera=False):
    run = Path(run)
    _require(object_id in ('target_box_a', 'target_box_b'), 'unknown object')
    carry = _rows(run / 'skills/carry.jsonl')
    starts = [row for row in carry if row.get('event') == 'start']
    finals = [row for row in carry if row.get('event') == 'follow_final']
    _require(len(starts) == len(finals) == 1, 'ambiguous carry start/final')
    session = starts[0].get('session')
    _require(starts[0].get('backend') == 'detachable_joint' and starts[0].get('object') == object_id
             and isinstance(session, str) and len(session) == 32, 'invalid carry identity')
    final = finals[0]
    follow = final['follow']
    _require(final.get('session') == follow.get('session') == session and
             final.get('object') == follow.get('object') == object_id, 'final session mismatch')
    _require(follow.get('active') is False and follow.get('fault') == '', 'fault or incomplete release')
    _require(follow.get('translation_limit_m') == .002 and
             math.isclose(follow.get('rotation_limit_rad', -1), math.pi / 180, abs_tol=1e-12),
             'follow tolerances changed')
    _require(0 <= follow['max_translation_m'] < .002 and
             0 <= follow['max_rotation_rad'] < math.pi / 180, 'observed drift exceeded limits')
    for skill in ('pick', 'place'):
        records = _rows(run / ('skills/%s.jsonl' % skill))
        _require(len(records) == 1 and records[0].get('object_name') == object_id and
                 str(records[0].get('outcome')) == '0', skill + ' result missing or failed')
        watch = records[0].get('joint_follow_watch') or {}
        _require(watch.get('session') == session and watch.get('fault') == '', skill + ' watch mismatch')
    lo, hi = follow['first_sim_ns'], follow['last_sim_ns']
    _require(isinstance(lo, int) and isinstance(hi, int) and 0 <= lo < hi, 'invalid trace bounds')
    frames = [row for row in _rows(run / 'data/physics.jsonl') if lo <= row['sim_ns'] <= hi]
    _require(len(frames) == follow['samples'] and len(frames) >= 2, 'physics frame count mismatch')
    _require(frames[0]['sim_ns'] == lo and frames[-1]['sim_ns'] == hi, 'missing boundary frames')
    _require((hi - lo) >= int(min_duration_s * 1e9), 'follow duration is shorter than declared')
    _require(all(b['sim_ns'] - a['sim_ns'] == 20_000_000 and
                 b['monotonic_ns'] > a['monotonic_ns'] for a, b in zip(frames, frames[1:])),
             'missing, reordered or non-50-Hz physical frames')
    steps = []
    if physics_step_ns is not None:
        _require((hi - lo) % physics_step_ns == 0, 'attachment boundaries do not align to physics steps')
        steps = [row for row in _rows(run / 'physics_steps.jsonl') if lo <= row['sim_ns'] <= hi]
        _require(len(steps) == (hi - lo) // physics_step_ns + 1 and
                 steps[0]['sim_ns'] == lo and steps[-1]['sim_ns'] == hi,
                 'missing per-step physics records')
        _require(all(row['step_ns'] == physics_step_ns for row in steps) and
                 all(b['sim_ns'] - a['sim_ns'] == physics_step_ns and
                     b['monotonic_ns'] > a['monotonic_ns'] for a, b in zip(steps, steps[1:])),
                 'per-step simulation clock is incomplete or unordered')
        by_time = {row['sim_ns']: row for row in steps}
        for row in frames:
            raw = by_time[row['sim_ns']]
            _require(raw['monotonic_ns'] == row['monotonic_ns'] and
                     raw['parent_pose'] == row['parent_pose'] and
                     raw['objects'] == row['objects'],
                     '50 Hz observation and per-step source disagree')
    ref = follow['first_relative_pose']
    _require(isinstance(ref, list) and len(ref) == 7, 'no measured attachment reference')
    peak_position = peak_angle = 0.
    for row in frames:
        if physics_step_ns is not None:
            _require(physics_step_ns == 2_000_000 and row.get('physics_steps') == 10 and
                     row.get('physics_min_step_ns') == row.get('physics_max_step_ns') == physics_step_ns and
                     row.get('physics_bad_time') is False and row.get('physics_missing_pose_steps') == 0 and
                     row.get('physics_nonfinite_pose') is False and
                     isinstance(row.get('physics_max_pose_jump_m'), (float, int)) and
                     math.isfinite(row['physics_max_pose_jump_m']) and 0 <= row['physics_max_pose_jump_m'] < 1.,
                     'physics-step timing or per-step pose continuity was not established')
            _require(row.get('contact_force_observed') is False, 'unexpected contact-force schema')
        obj = row['objects'][object_id]
        _require(obj.get('joint_component') is True, 'attachment missing in synchronous physics sample')
        position, quaternion = relative_pose(row['parent_pose'], obj['pose'])
        translation = math.dist(position, ref[:3])
        qnorm = math.sqrt(sum(x*x for x in ref[3:]))
        _require(math.isfinite(qnorm) and .999 <= qnorm <= 1.001, 'invalid reference quaternion')
        angle = 2 * math.acos(min(1., abs(sum(a*b for a, b in zip(quaternion, ref[3:])) / qnorm)))
        peak_position, peak_angle = max(peak_position, translation), max(peak_angle, angle)
        _require(translation < .002 and angle < math.pi / 180, 'independent SE(3) drift exceeded limits')
    previous = None
    for row in steps:
        obj = row['objects'][object_id]
        _require(obj.get('joint_component') is True, 'attachment missing in per-step sample')
        position, quaternion = relative_pose(row['parent_pose'], obj['pose'])
        translation = math.dist(position, ref[:3])
        qnorm = math.sqrt(sum(x*x for x in ref[3:]))
        angle = 2 * math.acos(min(1., abs(sum(a*b for a, b in zip(quaternion, ref[3:])) / qnorm)))
        _require(translation < .002 and angle < math.pi / 180, 'per-step SE(3) drift exceeded limits')
        peak_position, peak_angle = max(peak_position, translation), max(peak_angle, angle)
        pose_positions = [row['parent_pose'][:3]] + [row['objects'][name]['pose'][:3]
                          for name in ('target_box_a', 'target_box_b')]
        for name in ('target_box_a', 'target_box_b'):
            relative_pose(row['parent_pose'], row['objects'][name]['pose'])
        _require(row.get('contact_force_observed') is False, 'unexpected per-step contact-force schema')
        _require(all(all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
                         for x in point) for point in pose_positions), 'nonfinite per-step position')
        if previous is not None:
            _require(all(math.dist(a, b) < 1. for a, b in zip(pose_positions, previous)),
                     'per-step position jumped at least one metre')
        previous = pose_positions
    camera_frames = None
    if require_camera:
        from export_lerobot import episode
        _, camera, _ = episode(run)
        _require(all((run / 'data' / row['image']).is_file() for row in camera),
                 'a recorded camera image is missing')
        camera_frames = len(camera)
    return dict(status='FOLLOW_TRACE_PASS', object=object_id, session=session,
                attached_samples=len(frames), attached_duration_s=(hi-lo)/1e9,
                physics_step_samples=len(steps),
                max_translation_m=peak_position, max_rotation_rad=peak_angle,
                physics_step_ns=physics_step_ns, camera_frames=camera_frames, contact_force_observed=False,
                interpretation='50 Hz sampled functional evidence; not D3 or contact-grasp admission')
