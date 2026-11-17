"""Capture-time derivation: a frame belongs to the world at its own stamp.

WHY THIS SUITE EXISTS: the recorder used to write the callback time as the
capture time. When delivery is delayed, that records an instant at which the
world had already moved, and the pairing then looks perfect (gap 0) against the
wrong state. The cases below pin the corrected contract: the receipt time and the
capture time are separate facts, the capture time comes from the frame's own
simulation stamp through the traced physics clock, and a frame that cannot be
mapped is reported as UNKNOWN rather than given a plausible-looking guess.
"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULE = HERE / 'capture_time.py'


def load_module():
    spec = importlib.util.spec_from_file_location('capture_time_under_test', str(MODULE))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


recorder = load_module()


def write_jsonl(path, rows):
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))


class CaptureTimeCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='capture-times-')
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)
        self.offset = 1_000_000_000_000  # arbitrary monotonic -> wall offset

    def physics(self, anchors):
        write_jsonl(self.out / 'physics.jsonl',
                    [dict(sim_ns=sim, monotonic_ns=mono, schema_version=1)
                     for sim, mono in anchors])

    def frames(self, rows):
        write_jsonl(self.out / 'frames.jsonl', rows)

    def frame(self, **fields):
        row = dict(frame_index=0, sim_ns=10 ** 9, monotonic_ns=5,
                   received_wall_ns=self.offset + 12 * 10 ** 9,
                   image='images/000000.png', valid=True)
        row.update(fields)
        return row

    def test_capture_time_comes_from_the_frame_stamp_not_the_delivery(self):
        """The regression: a 2 s late frame must not be dated 2 s late.

        The world moved from x=.22 to x=.32 during the delay. Dating the frame by
        its arrival pairs it with x=.32; dating it by its own stamp pairs it with
        x=.22, which is where the object was when the picture was taken.
        """
        # Physics ran from sim 0 s to sim 20 s in real time.
        self.physics([(0, 0), (20 * 10 ** 9, 20 * 10 ** 9)])
        self.frames([self.frame(sim_ns=10 * 10 ** 9)])
        summary = recorder.capture_times(self.out, self.offset)
        row = json.loads((self.out / 'frames.jsonl').read_text().splitlines()[0])
        self.assertEqual(summary['resolved'], 1)
        self.assertEqual(summary['unknown'], 0)
        # Capture instant: 10 s of physics == 10 s of monotonic, not the 12 s arrival.
        self.assertEqual(row['captured_wall_ns'], self.offset + 10 * 10 ** 9)
        self.assertEqual(row['capture_time_source'], 'derived_from_physics_trace')
        # The arrival is still recorded, so the delay is visible instead of lost.
        self.assertEqual(row['received_wall_ns'], self.offset + 12 * 10 ** 9)
        self.assertEqual(row['received_wall_ns'] - row['captured_wall_ns'], 2 * 10 ** 9)

    def test_a_frame_before_the_trace_starts_is_unknown_not_extrapolated(self):
        self.physics([(10 * 10 ** 9, 10 * 10 ** 9), (20 * 10 ** 9, 20 * 10 ** 9)])
        self.frames([self.frame(sim_ns=5 * 10 ** 9)])
        summary = recorder.capture_times(self.out, self.offset)
        row = json.loads((self.out / 'frames.jsonl').read_text().splitlines()[0])
        self.assertIsNone(row['captured_wall_ns'])
        self.assertEqual(row['capture_time_source'], 'UNKNOWN')
        self.assertIn('outside the traced physics range', row['capture_time_reason'])
        self.assertEqual(summary['unknown'], 1)

    def test_a_run_without_a_physics_trace_is_unknown(self):
        self.frames([self.frame()])
        summary = recorder.capture_times(self.out, self.offset)
        row = json.loads((self.out / 'frames.jsonl').read_text().splitlines()[0])
        self.assertIsNone(row['captured_wall_ns'])
        self.assertIn('no physics trace', row['capture_time_reason'])

    def test_every_frame_is_rewritten_so_no_stale_capture_time_survives(self):
        """A row that already carried a capture time must be recomputed."""
        self.physics([(0, 0), (20 * 10 ** 9, 20 * 10 ** 9)])
        self.frames([self.frame(sim_ns=10 * 10 ** 9,
                                captured_wall_ns=self.offset + 12 * 10 ** 9,
                                capture_time_source='derived_from_physics_trace')])
        recorder.capture_times(self.out, self.offset)
        row = json.loads((self.out / 'frames.jsonl').read_text().splitlines()[0])
        self.assertEqual(row['captured_wall_ns'], self.offset + 10 * 10 ** 9)

    def test_an_absent_manifest_is_reported_not_invented(self):
        summary = recorder.capture_times(self.out, self.offset)
        self.assertEqual(summary['status'], 'NO_FRAME_MANIFEST')


if __name__ == '__main__':
    unittest.main()
