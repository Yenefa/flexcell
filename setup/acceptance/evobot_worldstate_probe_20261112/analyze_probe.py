"""Recompute diagnostic counts and motion brackets from the retained raw files.

This does not evaluate task acceptance. Brackets use receive timestamps and
include the printed offsets; no pose is interpolated to a phase boundary.
"""
import csv
import json
import math
from pathlib import Path
import statistics

base = Path(__file__).resolve().parent
root = base / 'gazebo'
all_rows = [json.loads(line) for line in (root / 'active/world_state.jsonl').read_text().splitlines()]
rows = [r for r in all_rows if r['channel'] == 'topic']
events = [json.loads(line) for line in (root / 'active/events.jsonl').read_text().splitlines()]
phases = [e for e in events if e['kind'] == 'PUSH_FEEDBACK']
moves = [json.loads(line) for line in (root / 'sim/skills/move_to_pose.jsonl').read_text().splitlines()]
names = {0: 'VALIDATING', 1: 'OBSERVING', 2: 'APPROACH', 3: 'PUSHING', 4: 'VERIFYING', 5: 'RETREATING'}


def stamp(row):
    value = row['world_state']['header']['stamp']
    return value['sec'], value['nanosec']


def red_x(row):
    return next(o for o in row['world_state']['objects'] if o['name'] == 'target_box_a')['pose']['position']['x']


def last_phase(utc_ns):
    earlier = [e for e in phases if e['rx_utc_ns'] <= utc_ns]
    return earlier[-1] if earlier else None


by_channel = {ch: {stamp(r): r['world_state'] for r in all_rows if r['channel'] == ch}
              for ch in ('topic', 'result')}
gaps = [(b['rx_mono_ns'] - a['rx_mono_ns']) / 1e9 for a, b in zip(rows, rows[1:])]
before = json.loads((root / 'gt_before.json').read_text())['objects']
after = json.loads((root / 'gt_after.json').read_text())['objects']
summary = dict(
    kind='INDEPENDENT_RECOMPUTATION_OF_RECORDED_PROBE',
    topic_samples=len(rows), result_samples=len(all_rows) - len(rows),
    distinct_topic_source_stamps=len(by_channel['topic']),
    topic_result_identical=by_channel['topic'] == by_channel['result'],
    usable_topic_samples=sum(not r['issues'] for r in rows),
    duration_between_first_last_topic_s=(rows[-1]['rx_mono_ns'] - rows[0]['rx_mono_ns']) / 1e9,
    max_topic_gap_s=max(gaps), median_topic_gap_s=statistics.median(gaps),
    max_object_age_s=max(o['pose_age_s'] for r in rows for o in r['world_state']['objects']),
    ee_min_xyz=[min(r['world_state']['robot']['ee_pose']['position'][k] for r in rows) for k in ('x', 'y', 'z')],
    ee_max_xyz=[max(r['world_state']['robot']['ee_pose']['position'][k] for r in rows) for k in ('x', 'y', 'z')],
    all_observed_carry_disengaged=all(not r['world_state']['carry']['engaged'] for r in rows),
    net_red_displacement_along_minus_x_m=before['target_box_a'][0] - after['target_box_a'][0],
    protected_blue_displacement_m=math.dist(before['target_box_b'][:3], after['target_box_b'][:3]),
    recovery_reported_achieved_m=json.loads((root / 'trial/recovery.json').read_text())['verdict']['achieved_m'],
    moves=[],
    limitations=[
        'WorldState is a sampled diagnostic, not a complete physics/contact evidence bundle.',
        'EE and gripper source timestamps are absent; receive times do not imply simultaneous sensing.',
        'push.jsonl was not retained: push_server has no profile log_dir entry and used its container default.',
        'MoveToPose logs, push feedback, individual results and raw WorldState messages WERE retained.',
        'New execution environment; do not pool this run with the previous nine.',
    ])
for move in moves:
    start, end = int(move['request_timestamp'] * 1e9), int(move['wall_ts'] * 1e9)
    phase = last_phase(start)
    pre = max((r for r in rows if r['rx_utc_ns'] <= start), key=lambda r: r['rx_utc_ns'], default=None)
    post = min((r for r in rows if r['rx_utc_ns'] >= end), key=lambda r: r['rx_utc_ns'], default=None)
    summary['moves'].append(dict(
        goal_uuid=phase['goal_uuid'] if phase else None,
        phase_at_dispatch=names[phase['feedback']['phase']] if phase else None,
        request_timestamp=move['request_timestamp'], wall_ts=move['wall_ts'],
        target=move['target']['position'], reached=move['reached_pose']['position'],
        outcome=move['outcome'], position_error_m=move['position_error_m'],
        orientation_error_rad=move['orientation_error_rad'], orientation_enforced=move['orientation_enforced'],
        bracket=dict(red_x_before_m=red_x(pre), red_x_after_m=red_x(post),
                     delta_x_m=red_x(post) - red_x(pre),
                     pre_offset_s=(start - pre['rx_utc_ns']) / 1e9,
                     post_offset_s=(post['rx_utc_ns'] - end) / 1e9) if pre and post else None))

with (base / 'analysis.json').open('x') as stream:
    json.dump(summary, stream, indent=2)
with (base / 'trajectory.csv').open('x') as stream:
    writer = csv.writer(stream)
    writer.writerow(['rx_mono_ns', 'rx_utc_ns', 'sim_sec', 'sim_nanosec', 'phase_at_rx', 'goal_uuid',
                     'ee_x', 'ee_y', 'ee_z', 'ee_qx', 'ee_qy', 'ee_qz', 'ee_qw', 'gripper_position',
                     'red_x', 'red_y', 'red_z', 'red_age_s', 'blue_x', 'blue_y', 'blue_z', 'blue_age_s'])
    for row in rows:
        world = row['world_state']
        robot = world['robot']
        p, q = robot['ee_pose']['position'], robot['ee_pose']['orientation']
        objects = {obj['name']: obj for obj in world['objects']}
        phase = last_phase(row['rx_utc_ns'])
        writer.writerow([row['rx_mono_ns'], row['rx_utc_ns'], *stamp(row),
                         names[phase['feedback']['phase']] if phase else '',
                         phase['goal_uuid'] if phase else '',
                         *[p[k] for k in ('x', 'y', 'z')], *[q[k] for k in ('x', 'y', 'z', 'w')],
                         robot['gripper_position'],
                         *[objects['target_box_a']['pose']['position'][k] for k in ('x', 'y', 'z')],
                         objects['target_box_a']['pose_age_s'],
                         *[objects['target_box_b']['pose']['position'][k] for k in ('x', 'y', 'z')],
                         objects['target_box_b']['pose_age_s']])
print(json.dumps(summary, indent=2))
