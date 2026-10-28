#!/usr/bin/env python3
"""Audit frozen replay facts; does not run or qualify the workcell."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify():
    inputs = json.loads((HERE / 'inputs.json').read_text())
    raw = (HERE / 'report.json').read_bytes()
    assert sha(raw) == inputs['raw_report_sha256']
    report = json.loads(raw)
    assert report['status'] == 'PASS' and report['physical_tasks'] == 0
    assert report['learning_dataset_published'] is False
    assert len(report['candidates']) == 5
    pixels = json.loads((HERE / 'pixel-check.json').read_text())
    assert pixels['status'] == 'PASS' and pixels['total_verified'] == 2445
    assert report['archive_sha256'] == json.loads((HERE / 'original-camera-diagnosis.json').read_text())['archive_sha256']
    total = 0
    for index, item in enumerate(report['candidates'], 1):
        meta = inputs['frames']['candidate-%02d' % index]
        compressed = (HERE / meta['manifest']).read_bytes()
        assert sha(compressed) == meta['manifest_sha256']
        decoded = gzip.decompress(compressed)
        assert sha(decoded) == meta['frames_sha256']
        rows = [json.loads(line) for line in decoded.splitlines()]
        assert len(rows) == item['source_frames'] == item['recorded_frames']
        assert [r['frame_index'] for r in rows] == list(range(len(rows)))
        stamps = [r['sim_ns'] for r in rows]
        source = pixels['candidates'][index - 1]
        assert source['source_stamps_ns'] == stamps
        assert sha(json.dumps(stamps, separators=(',', ':')).encode()) == source['source_stamps_sha256']
        assert source['pixels_verified'] == len(rows) and source['pixel_mismatches'] == 0
        assert len(meta['images_sha256']) == len(rows)
        assert all(row['image'] in meta['images_sha256'] for row in rows)
        assert item['all_source_stamps_in_order'] is True
        assert not item['missing_source_stamps_ns'] and item['missing_images'] == 0
        assert item['writer']['drain_completed'] is True and not item['writer']['errors']
        assert not item['writer']['rejected_frames']
        assert item['source_script_sha256'] == inputs['source_sha256']['scripts/record_sim_data.py']
        lo, hi = item['original_recording_source_interval_ns']
        selected = [row for row in rows if lo <= row['sim_ns'] <= hi]
        assert len(selected) == item['source_frames_in_interval'] == item['recorded_frames_in_interval']
        assert item['invalid_frames_in_interval'] == 0
        for row in selected:
            assert row['valid'] is True and not row['reasons']
            assert all(math.isfinite(v) for v in row['observation.state'] + row['action'])
            for key in ('state', 'controller_reference'):
                assert 0 <= row['sim_ns'] - row[key]['sim_ns'] <= 50_000_000
            assert 0 <= row['sim_ns'] - row['gripper_target']['sim_ns'] <= 600_000_000_000
        total += len(selected)
    assert total == 718
    baseline = report['baseline']
    assert baseline['recorded_frames'] == 480 and baseline['source_frames'] == 504
    assert len(baseline['missing_source_stamps_ns']) == 24
    assert baseline['invalid_frames_in_interval'] == 34
    integration = json.loads((HERE / 'integration.json').read_text())
    assert integration['default_joint_admission'] == 'NO_GO_FOR_DEFAULT_ADMISSION'
    for name, expected in integration['byte_identical_inputs'].items():
        data = (ROOT / name).read_bytes()
        assert sha(data) == expected['sha256'] and len(data) == expected['bytes'], name
    return dict(status='ARCHIVED_REPLAY_FACTS_VERIFIED', source_frames=2445,
                aligned_context_frames=718, preserved_source_inputs=25,
                physical_tasks=0, joint_default_admission='NO_GO')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--current-source', action='store_true')
    args = parser.parse_args()
    result = verify()
    if args.current_source:
        for name, digest in json.loads((HERE / 'inputs.json').read_text())['source_sha256'].items():
            assert sha((ROOT / name).read_bytes()) == digest, name
    print(json.dumps(result))
