#!/usr/bin/env python3
"""Convert declared raw episodes using the official LeRobot v0.6.1 writer.

No robot connection, model, training, Hub upload or hardware replay is used.
Actual source timestamps are preserved as explicit int64 features; LeRobot's
standard timestamp is its documented frame_index/fps sampling clock.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

JOINTS = ['joint1', 'joint2', 'joint3', 'joint4', 'gripper_left_joint']


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def episode(run):
    """Reject gaps/missing aligned data instead of silently selecting good frames."""
    result = json.loads((run / 'result.json').read_text())
    collection = json.loads((run / 'data/collection.json').read_text())
    if collection['errors'] or collection['rosbag_exit'] != 0:
        raise ValueError('raw collection has errors: ' + str(run))
    if not result.get('task') or not result.get('runtime_fingerprint'):
        raise ValueError('task outcome or fingerprint absent')
    start = result.get('recording_start_monotonic_ns', result['task_start_monotonic_ns'])
    end = result.get('recording_end_monotonic_ns', result['task_end_monotonic_ns'])
    rows = [json.loads(line) for line in (run / 'data/frames.jsonl').read_text().splitlines()]
    rows = [row for row in rows if start <= row['monotonic_ns'] <= end]
    if len(rows) < 2 or any(row['valid'] is not True for row in rows):
        raise ValueError('task has incomplete aligned RGB/state/action data: ' + str(run))
    if any(not 85_000_000 <= b['sim_ns'] - a['sim_ns'] <= 115_000_000 for a, b in zip(rows, rows[1:])):
        raise ValueError('camera sampling gaps; original data retained: ' + str(run))
    inputs = {str(p.relative_to(run)): digest(p) for p in run.rglob('*')
              if p.is_file() and p.name != 'stack.log'}
    return result, rows, inputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True, help='Declared run directories, including failures')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    import numpy as np
    import torch
    from PIL import Image
    from lerobot.datasets.lerobot_dataset import LeRobotDataset
    if sys.version_info[:2] != (3, 12) or np.__version__.split('.')[0] != '2':
        raise RuntimeError('use the isolated Python 3.12 / NumPy 2 data environment')
    if importlib.metadata.version('lerobot') != '0.6.1' or torch.version.cuda is not None:
        raise RuntimeError('LeRobot 0.6.1 and CPU-only PyTorch required')
    manifest = json.loads(args.manifest.read_text())
    runs = [Path(item['run']) for item in manifest['episodes']]
    if len(runs) != len(set(runs)) or not runs:
        raise ValueError('empty or duplicate declared episodes')
    prepared = [episode(run) for run in runs]  # preflight all; never omit a failed episode
    features = {
        'observation.images.rgb': {'dtype': 'video', 'shape': (480, 640, 3), 'names': ['height', 'width', 'channels']},
        'observation.state': {'dtype': 'float32', 'shape': (5,), 'names': JOINTS},
        'action': {'dtype': 'float32', 'shape': (5,), 'names': JOINTS},
    }
    for name in ('camera', 'state', 'reference', 'gripper'):
        features['source.' + name + '_sim_ns'] = {'dtype': 'int64', 'shape': (1,), 'names': ['sim_ns']}
    dataset = LeRobotDataset.create(repo_id='flexcell/local-simulation', root=args.out,
        fps=10, features=features, robot_type='open_manipulator_x', use_videos=True, video_backend='pyav')
    provenance = dict(schema_version=1, manifest_sha256=digest(args.manifest),
        action_semantics='arm controller reference positions (rad) + held accepted gripper target (m)',
        timestamp_semantics='timestamp=frame_index/10; source.*_sim_ns retain original simulation stamps',
        observation_source='SIMULATION_GROUND_TRUTH; RGB is data-only',
        episodes=[], environment={dist.metadata['Name']: dist.version for dist in importlib.metadata.distributions()})
    expected = []
    for run, declared, (result, rows, inputs) in zip(runs, manifest['episodes'], prepared):
        task = declared['task']
        for row in rows:
            image = np.asarray(Image.open(run / 'data' / row['image']).convert('RGB'))
            values = {'observation.images.rgb': image,
                      'observation.state': np.asarray(row['observation.state'], dtype=np.float32),
                      'action': np.asarray(row['action'], dtype=np.float32), 'task': task}
            for name, stamp in [('camera', row['sim_ns']), ('state', row['state']['sim_ns']),
                                ('reference', row['controller_reference']['sim_ns']),
                                ('gripper', row['gripper_target']['sim_ns'])]:
                values['source.' + name + '_sim_ns'] = np.asarray([stamp], dtype=np.int64)
            dataset.add_frame(values)
            expected.append((row['observation.state'], row['action'], dict(
                camera=row['sim_ns'], state=row['state']['sim_ns'],
                reference=row['controller_reference']['sim_ns'], gripper=row['gripper_target']['sim_ns'])))
        dataset.save_episode()
        provenance['episodes'].append(dict(index=len(provenance['episodes']), task=task,
            frames=len(rows), runtime=result, raw_inputs=inputs))
    dataset.finalize()
    with (args.out / 'flexcell_provenance.json').open('x') as stream:
        json.dump(provenance, stream, indent=2, allow_nan=False)
    # Readback through the official loader; does not invoke lerobot-replay.
    loaded = LeRobotDataset('flexcell/local-simulation', root=args.out, video_backend='pyav')
    if len(loaded) != len(expected) or loaded.num_episodes != len(runs):
        raise RuntimeError('official loader frame/episode count mismatch')
    for index, (state, action, stamps) in enumerate(expected):
        row = loaded.get_raw_item(index)
        if not np.allclose(np.asarray(row['observation.state']), state, atol=1e-6):
            raise RuntimeError('state roundtrip mismatch')
        if not np.allclose(np.asarray(row['action']), action, atol=1e-6):
            raise RuntimeError('action roundtrip mismatch')
        for name, stamp in stamps.items():
            if int(np.asarray(row['source.' + name + '_sim_ns']).reshape(-1)[0]) != stamp:
                raise RuntimeError('source timestamp roundtrip mismatch: ' + name)
    for index in {0, len(loaded) - 1}:
        if tuple(loaded[index]['observation.images.rgb'].shape) != (3, 480, 640):
            raise RuntimeError('official video loader shape mismatch')
    report = dict(status='ROUNDTRIP_PASS', episodes=len(runs), frames=len(expected),
                  provenance_sha256=digest(args.out / 'flexcell_provenance.json'))
    (args.out / 'roundtrip.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
