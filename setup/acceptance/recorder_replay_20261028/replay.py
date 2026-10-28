#!/usr/bin/env python3
"""Replay preserved telemetry into the recorder, without simulator or actuators.

One affected bag is replayed through the old callback and all five bags through
the candidate. The same deterministic encoder stalls stress both versions.
No robot task, command publisher, replacement trial or new learning dataset.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
from zipfile import ZipFile

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

ROOT = Path(__file__).resolve().parents[3]
TOPICS = {'/clock', '/joint_states', '/arm_controller/controller_state',
          '/flexcell/execution_command', '/flexcell/physics_trace', '/flexcell/camera/rgb'}


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path, label):
    sys.path.insert(0, str(ROOT / 'scripts'))
    spec = importlib.util.spec_from_file_location('recorder_' + label, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    encode = module.write_png
    calls = 0
    def stalled(path, message):
        nonlocal calls
        calls += 1
        if calls % 30 == 0:
            time.sleep(.8)
        encode(path, message)
    module.write_png = stalled
    return module


def source(db):
    with sqlite3.connect(str(db)) as connection:
        topics = {i: (name, get_message(kind)) for i, name, kind in
                  connection.execute('SELECT id,name,type FROM topics') if name in TOPICS}
        camera = next(i for i, (name, _) in topics.items() if name == '/flexcell/camera/rgb')
        stamps = []
        for (data,) in connection.execute('SELECT data FROM messages WHERE topic_id=? ORDER BY timestamp', (camera,)):
            msg = deserialize_message(data, topics[camera][1])
            stamps.append(msg.header.stamp.sec * 10**9 + msg.header.stamp.nanosec)
    return topics, stamps


def replay(db, out, script, label, interval):
    out.mkdir(parents=True, exist_ok=False)
    topics, expected = source(db)
    module = load(script, label)
    recorder = module.Recorder(out)
    publisher = Node('offline_recorder_replay')
    publishers = {}
    for i, (name, kind) in topics.items():
        qos = QoSProfile(depth=100)
        if name == '/flexcell/camera/rgb':
            qos.reliability = ReliabilityPolicy.BEST_EFFORT
        if name == '/flexcell/execution_command':
            qos.durability = DurabilityPolicy.TRANSIENT_LOCAL
        publishers[i] = publisher.create_publisher(kind, name, qos)
    executor = SingleThreadedExecutor()
    executor.add_node(recorder)
    done, stop, errors = threading.Event(), threading.Event(), []
    def produce():
        try:
            with sqlite3.connect(str(db)) as connection:
                query = 'SELECT timestamp,topic_id,data FROM messages ORDER BY timestamp'
                begin = connection.execute('SELECT MIN(timestamp) FROM messages').fetchone()[0]
                wall = time.monotonic()
                for stamp, topic, data in connection.execute(query):
                    if topic not in topics:
                        continue
                    if stop.wait(max(0, wall + (stamp - begin) / 1e9 - time.monotonic())):
                        break
                    publishers[topic].publish(deserialize_message(data, topics[topic][1]))
        except Exception as exc:
            errors.append(str(exc))
        finally:
            done.set()
    worker = threading.Thread(target=produce, daemon=True)
    try:
        deadline = time.monotonic() + 5
        while not all(pub.get_subscription_count() for pub in publishers.values()):
            if time.monotonic() > deadline:
                raise RuntimeError('isolated telemetry subscriptions did not match')
            executor.spin_once(timeout_sec=.05)
        worker.start()
        deadline = time.monotonic() + 180
        while not done.is_set():
            executor.spin_once(timeout_sec=.02)
            if time.monotonic() > deadline:
                raise RuntimeError('bounded offline replay timed out')
        tail = time.monotonic() + 2
        while time.monotonic() < tail:
            executor.spin_once(timeout_sec=.02)
    finally:
        stop.set()
        if worker.ident is not None:
            worker.join(5)
        if hasattr(recorder, 'writer'):
            recorder.writer.close()
            errors.extend(recorder.writer.report()['errors'])
            writer = recorder.writer.report()
        else:
            recorder.frames.close()
            writer = None
        recorder.physics.close()
        errors.extend(recorder.errors)
        executor.remove_node(recorder)
        executor.shutdown()
        recorder.destroy_node()
        publisher.destroy_node()
    if errors:
        raise RuntimeError('offline recording failed: ' + repr(errors))
    rows = [json.loads(line) for line in (out / 'frames.jsonl').read_text().splitlines()]
    actual = [row['sim_ns'] for row in rows]
    selected = [row for row in rows if interval[0] <= row['sim_ns'] <= interval[1]]
    expected_selected = [stamp for stamp in expected if interval[0] <= stamp <= interval[1]]
    report = dict(version=label, source_script_sha256=sha(script), source_frames=len(expected),
                  recorded_frames=len(rows), all_source_stamps_in_order=actual == expected,
                  missing_source_stamps_ns=sorted(set(expected) - set(actual)),
                  original_recording_source_interval_ns=interval,
                  source_frames_in_interval=len(expected_selected),
                  recorded_frames_in_interval=len(selected),
                  invalid_frames_in_interval=sum(not row['valid'] for row in selected),
                  missing_images=sum(not (out / row['image']).is_file() for row in rows),
                  writer=writer)
    (out / 'replay-result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('writer', 'missing_source_stamps_ns')}), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--baseline-script', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--domain', type=int, default=169)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(kind='OFFLINE_TELEMETRY_REPLAY_NOT_PHYSICAL_QUALIFICATION',
                  archive_sha256=sha(args.archive), physical_tasks=0, learning_dataset_published=False,
                  stress=dict(encoder_stall_s=.8, every_n_images=30), domain=args.domain, candidates=[])
    rclpy.init(domain_id=args.domain)
    try:
        with ZipFile(args.archive) as archive, tempfile.TemporaryDirectory(dir=args.out) as tmp:
            results = sorted(n for n in archive.namelist() if n.endswith('/result.json'))
            for i, name in enumerate(results):
                base = name[:-len('result.json')]
                frames_name = base + 'data/frames.jsonl'
                if frames_name not in archive.namelist():
                    continue
                raw = json.loads(archive.read(name))
                lo = raw.get('recording_start_monotonic_ns', raw['task_start_monotonic_ns'])
                hi = raw.get('recording_end_monotonic_ns', raw['task_end_monotonic_ns'])
                frames = [json.loads(line) for line in archive.read(frames_name).splitlines()]
                rows = [row for row in frames if lo <= row['monotonic_ns'] <= hi]
                interval = [rows[0]['sim_ns'], rows[-1]['sim_ns']]
                db = Path(tmp) / 'raw.db3'
                db.write_bytes(archive.read(base + 'data/raw/raw_0.db3'))
                if not report.get('baseline'):
                    report['baseline'] = replay(db, args.out / 'baseline', args.baseline_script, 'baseline', interval)
                result = replay(db, args.out / ('candidate-%02d' % (i + 1)),
                                ROOT / 'scripts/record_sim_data.py', 'candidate', interval)
                result['original_run'] = base
                report['candidates'].append(result)
                db.unlink()
        report['status'] = ('PASS' if report['baseline']['missing_source_stamps_ns']
            and len(report['candidates']) == 5 and all(
                r['all_source_stamps_in_order'] and not r['invalid_frames_in_interval']
                and not r['missing_images'] for r in report['candidates']) else 'FAIL')
    except Exception as exc:
        report.update(status='FAIL', error=str(exc))
    finally:
        rclpy.shutdown()
        (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'report': str(args.out / 'report.json')}))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
