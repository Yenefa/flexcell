"""Slow or broken image storage must not silently remove source frames."""
import importlib.util
import json
from pathlib import Path
import threading


def writer_type():
    path = Path(__file__).resolve().parents[4] / 'scripts/frame_writer.py'
    spec = importlib.util.spec_from_file_location('frame_writer', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FrameWriter


def row(index):
    return dict(frame_index=index, sim_ns=index * 100_000_000, monotonic_ns=index + 1,
                image='%d.png' % index, valid=False, reasons=[], action=[index, .5])


def test_slow_encoder_keeps_all_source_stamps_and_actions(tmp_path):
    entered, release = threading.Event(), threading.Event()
    def encode(path, value):
        entered.set()
        assert release.wait(5)
        path.write_bytes(bytes([value]))
    writer = writer_type()(tmp_path, encode, max_pending=8)
    try:
        assert writer.submit(row(0), 0)
        assert entered.wait(2)
        # Storage is deliberately blocked while the callback-side work completes.
        for i in range(1, 8):
            assert writer.submit(row(i), i)
    finally:
        release.set()
        assert writer.close()
    saved = [json.loads(line) for line in (tmp_path / 'frames.jsonl').read_text().splitlines()]
    assert [x['sim_ns'] for x in saved] == [i * 100_000_000 for i in range(8)]
    assert [x['action'] for x in saved] == [[i, .5] for i in range(8)]
    assert all(x['valid'] for x in saved)
    assert writer.report()['frames_written'] == 8


def test_queue_overflow_is_explicit_collection_failure(tmp_path):
    entered, release = threading.Event(), threading.Event()
    def encode(path, value):
        entered.set()
        assert release.wait(5)
        path.write_bytes(b'fixture')
    writer = writer_type()(tmp_path, encode, max_pending=1)
    try:
        assert writer.submit(row(0), 0)
        assert entered.wait(2)
        assert writer.submit(row(1), 1)
        assert not writer.submit(row(2), 2)
    finally:
        release.set()
        assert not writer.close()
    report = writer.report()
    assert report['drain_completed']
    assert report['rejected_frames'][0]['frame_index'] == 2
    assert 'image_writer_queue_full' in report['errors'][0]
    assert report['frames_written'] == 2


def test_encoder_failure_cannot_leave_a_valid_frame(tmp_path):
    def encode(path, value):
        raise OSError('disk full fixture')
    writer = writer_type()(tmp_path, encode)
    assert writer.submit(row(0), None)
    assert not writer.close()
    saved = json.loads((tmp_path / 'frames.jsonl').read_text())
    assert saved['valid'] is False
    assert 'disk full fixture' in saved['reasons'][0]
    assert writer.report()['valid_frames'] == 0


def test_incomplete_drain_is_rejected(tmp_path):
    entered, release = threading.Event(), threading.Event()
    def encode(path, value):
        entered.set()
        assert release.wait(5)
        path.write_bytes(b'fixture')
    writer = writer_type()(tmp_path, encode)
    try:
        assert writer.submit(row(0), None)
        assert entered.wait(2)
        assert not writer.close(timeout=.01)
        assert not writer.report()['drain_completed']
        assert 'image_writer_drain_incomplete' in writer.report()['errors']
        assert not writer.submit(row(1), None)
    finally:
        release.set()
        writer.worker.join(2)
