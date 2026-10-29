#!/usr/bin/env python3
"""Recheck the two recorded tasks offline; --video decodes every original RGB frame."""
import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'src/flexcell/flexcell_skills'))
from joint_follow_gate import verify_run
from export_lerobot import episode


def require(value, detail):
    if not value:
        raise ValueError(detail)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode_rgb(run, metadata):
    video = run / 'data/rgb-lossless.mkv'
    require(digest(video) == metadata['video_sha256'], 'video bytes changed')
    command = ['ffmpeg', '-nostdin', '-v', 'error', '-i', str(video), '-vsync', '0']
    proc = subprocess.Popen(command + ['-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for row in metadata['frames']:
            pixels = proc.stdout.read(640 * 480 * 3)
            require(len(pixels) == 640 * 480 * 3 and
                    hashlib.sha256(pixels).hexdigest() == row['rgb_sha256'],
                    'missing or changed decoded RGB frame: ' + row['image'])
        require(proc.stdout.read(1) == b'', 'extra decoded RGB frame')
        error = proc.stderr.read()
        require(proc.wait(timeout=30) == 0, 'video decoder failed: ' + error.decode(errors='replace'))
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)
    # Materialize lossless pixels for the existing camera-file gate. Original
    # PNG byte hashes remain in the receipt; re-encoded PNG bytes may differ.
    (run / 'data/images').mkdir()
    subprocess.run(command + ['-pix_fmt', 'rgb24', '-start_number', '0',
        str(run / 'data/images/%06d.png')], check=True, timeout=120, capture_output=True)
    return len(metadata['frames'])


def verify(check_video=False):
    archive_root = Path(__file__).resolve().parent
    receipt_path = archive_root / 'follow_ef959c6_receipt.json'
    require(digest(receipt_path) == 'b0f09728f867a6625f2abda3bdaf5f369dc503d20f0232cdd102be78ffea6c5a',
            'recorded receipt changed')
    receipt = json.loads(receipt_path.read_text())
    require(len(receipt['videos']) == 2, 'camera episode count changed')
    archive = archive_root / 'follow_ef959c6.zip'
    require(digest(archive) == receipt['archive_sha256'], 'recorded archive changed')
    facts, rgb_frames = [], 0
    with tempfile.TemporaryDirectory(prefix='flexcell-follow-audit-') as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(archive) as zipped:
            names = zipped.namelist()
            require(len(names) == len(set(names)) and set(names) == set(receipt['archived_files_sha256']),
                    'archive file set differs')
            require(all(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts
                        for name in names), 'unsafe archive path')
            zipped.extractall(root)
        for name, sha in receipt['archived_files_sha256'].items():
            require(digest(root / name) == sha, 'archive member changed: ' + name)
        window = json.loads((root / 'window.json').read_text())
        require(window['status'] == 'FUNCTIONAL_WINDOW_PASS' and window['no_replacements'] is True and
                window['runtime_fingerprint'] == receipt['runtime_fingerprint'] and
                [row['object'] for row in window['episodes']] == ['target_box_a', 'target_box_b'],
                'window outcome, order or identity changed')
        require(digest(root / 'declaration.json') == receipt['declaration_sha256'], 'declaration changed')
        for item, video in zip(window['episodes'], receipt['videos']):
            run = root / video['run']
            result = json.loads((run / 'result.json').read_text())
            require(result == item['result'] and result['status'] == 'PASS' and
                    result['physical_tasks_dispatched'] == 1 and result['task']['outcome_val'] == 0 and
                    result['runtime_fingerprint'] == receipt['runtime_fingerprint'], 'task result changed')
            identity = json.loads((run / 'identity.stdout').read_text())
            require(identity['source_revision'] == receipt['source_revision'] and
                    identity['source_tree_sha256'] == receipt['source_tree_sha256'] and
                    identity['mismatches'] == [] and identity.get('launch_files'), 'source/install identity differs')
            health = json.loads((run / 'health_after.stdout').read_text())
            require(health['ok'] is True and health['hard_fail'] == [] and len(health['checks']) == 19 and
                    health['checks']['task_state'] == 'IDLE' and health['checks']['carry_engaged'] is False,
                    'post-task health differs')
            metadata = json.loads((run / 'data/rgb-pixels.json').read_text())
            frames = [json.loads(line) for line in (run / 'data/frames.jsonl').read_text().splitlines()]
            require(len(frames) == video['frames'] and
                    [row['image'] for row in frames] == [row['image'] for row in metadata['frames']] and
                    [row['frame_index'] for row in frames] == list(range(len(frames))) and
                    metadata['width'] == 640 and metadata['height'] == 480, 'full camera frame set differs')
            if check_video:
                rgb_frames += decode_rgb(run, metadata)
            actual = verify_run(run, item['object'], min_duration_s=10., physics_step_ns=2_000_000,
                                require_camera=check_video)
            _, aligned, _ = episode(run)
            actual['camera_frames'] = len(aligned)
            expected = item['follow_evidence']
            require(actual.keys() == expected.keys(), 'follow result schema changed')
            for key, value in expected.items():
                equal = math.isclose(actual[key], value, rel_tol=0., abs_tol=1e-12) if type(value) is float else actual[key] == value
                require(equal, 'independent follow result differs: ' + key)
            facts.append(actual)
    return dict(status='PHYSICS_AND_RGB_EVIDENCE_REPRODUCED' if check_video else 'PHYSICS_EVIDENCE_REPRODUCED',
                source_revision=receipt['source_revision'], window_id=receipt['window_id'],
                tasks=2, follow=facts, all_rgb_pixels_verified=rgb_frames if check_video else None,
                original_png_and_rosbag_retention='full raw archive; see receipt for hashes and location',
                functional_only=True, default_admission='NO_GO')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', action='store_true', help='requires ffmpeg; no simulation is started')
    args = parser.parse_args()
    print(json.dumps(verify(args.video), indent=2, allow_nan=False))
