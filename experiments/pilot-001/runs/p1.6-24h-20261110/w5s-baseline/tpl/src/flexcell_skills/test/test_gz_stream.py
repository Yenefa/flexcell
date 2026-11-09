"""Offline guards for the gz Pose_V ground-truth stream (T6 / gate_flood).

The flood that `lib_gate.sh`'s `gate_flood` used to fail on was not cosmetic:
when a ``Pose_V`` message parsed but its nested class was missing from the
protobuf pool, ``for ent in msg.pose`` raised

    TypeError: No message class registered for 'gz.msgs.Pose'

inside gz-transport's python shim, which prints a **full traceback per
message** (to fd 1 inside the admin process) - ~900-1000 lines per reset.  The
same committed delivery-host artifacts carry it (963-1030 count), so the gate
had never been green on any recorded run.

The invariant these tests pin down:

- ``_on_pose_v`` **never raises** - a failing stream is counted and the
  staleness check rebuilds the subscription, with no traceback noise.
- a failing callback does not update ``last_rx`` (so self-heal can fire) and
  does not signal "first data seen".
- ``gz_stream_health()`` reports registration + the error count for the admin
  health/reset output.

Pure python: no rclpy, no running simulator.
"""

import unittest

from flexcell_skills import common


class _Pos:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class _Quat:
    def __init__(self, x, y, z, w):
        self.x, self.y, self.z, self.w = x, y, z, w


class _Ent:
    def __init__(self, name, x, y, z):
        self.name = name
        self.position = _Pos(x, y, z)
        self.orientation = _Quat(0.0, 0.0, 0.0, 1.0)


class _GoodMsg:
    """A Pose_V stand-in whose nested `pose` field iterates fine."""

    def __init__(self, ents):
        self.pose = [_Ent(*e) for e in ents]


class _BrokenMsg:
    """Mimics the flood: touching `.pose` raises like an unregistered class."""

    @property
    def pose(self):
        raise TypeError(
            "No message class registered for 'gz.msgs.Pose'")


class _ExplodingEnt:
    name = 'target_box_a'
    position = _Pos(0, 0, 0)
    orientation = _Quat(0, 0, 0, 1)


class _HalfBrokenMsg:
    """`pose` is iterable, but iterating yields a bad entry."""

    @property
    def pose(self):
        return [object()]


class TestPoseVCallback(unittest.TestCase):
    def setUp(self):
        self._saved = dict(common._GZ_STREAM)
        with common._GZ_STREAM['lock']:
            common._GZ_STREAM['poses'] = {}
            common._GZ_STREAM['last_rx'] = 0.0
            common._GZ_STREAM['cb_errors'] = 0
            common._GZ_STREAM['cb_error'] = ''

    def tearDown(self):
        with common._GZ_STREAM['lock']:
            common._GZ_STREAM.update(self._saved)

    def test_good_message_is_absorbed(self):
        rc = common._on_pose_v(_GoodMsg([('target_box_a', 0.22, 0.0, 0.0175)]))
        self.assertEqual(rc, 1)
        with common._GZ_STREAM['lock']:
            self.assertIn('target_box_a', common._GZ_STREAM['poses'])
            pos, quat, seen = common._GZ_STREAM['poses']['target_box_a']
            self.assertAlmostEqual(pos[0], 0.22, places=6)
            self.assertEqual(len(quat), 4)
            self.assertGreater(seen, 0.0)
            self.assertEqual(common._GZ_STREAM['cb_errors'], 0)

    def test_unregistered_nested_class_does_not_raise(self):
        """The flood invariant: no exception escapes into the transport."""
        try:
            rc = common._on_pose_v(_BrokenMsg())
        except Exception as exc:  # noqa: BLE001 - the regression itself
            self.fail('_on_pose_v raised %r - this is the traceback flood'
                      % (exc,))
        self.assertEqual(rc, 0)
        with common._GZ_STREAM['lock']:
            self.assertEqual(common._GZ_STREAM['cb_errors'], 1)
            self.assertIn('TypeError', common._GZ_STREAM['cb_error'])
            # a failing stream must look stale so self-heal rebuilds it
            self.assertEqual(common._GZ_STREAM['last_rx'], 0.0)

    def test_malformed_entry_does_not_raise(self):
        self.assertEqual(common._on_pose_v(_HalfBrokenMsg()), 0)
        with common._GZ_STREAM['lock']:
            self.assertEqual(common._GZ_STREAM['cb_errors'], 1)

    def test_first_data_event_only_on_success(self):
        class _Ev:
            def __init__(self):
                self.was_set = False

            def set(self):
                self.was_set = True

        good, bad = _Ev(), _Ev()
        common._on_pose_v(_BrokenMsg(), good)
        self.assertFalse(good.was_set)
        common._on_pose_v(_GoodMsg([('target_box_b', 0.2, -0.18, 0.0175)]), bad)
        self.assertTrue(bad.was_set)

    def test_error_counter_accumulates_across_messages(self):
        for _ in range(5):
            common._on_pose_v(_BrokenMsg())
        with common._GZ_STREAM['lock']:
            self.assertEqual(common._GZ_STREAM['cb_errors'], 5)

    def test_health_reports_registration_and_errors(self):
        registered, errors, last = common.gz_stream_health()
        self.assertIsInstance(registered, bool)
        self.assertEqual(errors, 0)
        self.assertEqual(last, '')
        common._on_pose_v(_BrokenMsg())
        _r, errors, last = common.gz_stream_health()
        self.assertEqual(errors, 1)
        self.assertIn('gz.msgs.Pose', last)

    def test_registration_happened_at_import(self):
        """Registration is a module-import side effect, not a thread race."""
        self.assertIsInstance(common._GZ_MSGS_REGISTERED, bool)
        if common._GZ_MSGS_REGISTERED:
            from gz.msgs10 import pose_pb2  # noqa: F401
            from google.protobuf import descriptor_pool
            pool = descriptor_pool.Default()
            self.assertIsNotNone(
                pool.FindMessageTypeByName('gz.msgs.Pose'),
                'gz.msgs.Pose must be resolvable in the default pool')


if __name__ == '__main__':
    unittest.main()
