"""Engage/release pairing and sampling rules for the carry-offset probe."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import recorder as rec  # noqa: E402

IDENTITY = (0.0, 0.0, 0.0, 1.0)
T0 = 1_000_000_000
PERIOD = 50_000_000  # 20 Hz


def snapshot(revision=1, object_pose=((0.1, 0.0, 0.0), IDENTITY),
             available=True, age=0.02, source='SIMULATION_GROUND_TRUTH'):
    return dict(
        revision=revision,
        source=source,
        objects={'target_box_a': dict(pose=object_pose, available=available,
                                      pose_age_s=age)},
        robot=dict(ee_frame='end_effector_link',
                   ee_pose=((0.0, 0.0, 0.0), IDENTITY)),
    )


def snapshot_with(names, revision=1):
    return dict(
        revision=revision,
        source='SIMULATION_GROUND_TRUTH',
        objects={name: dict(pose=((0.1, 0.0, 0.0), IDENTITY),
                            available=True, pose_age_s=0.02) for name in names},
        robot=dict(ee_frame='end_effector_link',
                   ee_pose=((0.0, 0.0, 0.0), IDENTITY)),
    )


class EngageReleaseTest(unittest.TestCase):
    def setUp(self):
        self.r = rec.CarryOffsetRecorder('target_box_a')
        self.r.on_world(snapshot())

    def test_engage_emits_one_event_row(self):
        self.r.on_carry(True, 'session-1', T0, backend='velocity_servo')
        self.r.on_carry(True, 'session-1', T0 + PERIOD)
        self.assertEqual([row['event'] for row in self.r.rows], ['engage'])
        row = self.r.rows[0]
        self.assertEqual(row['object'], 'target_box_a')
        self.assertEqual(row['carry_session'], 'session-1')
        self.assertEqual(row['backend'], 'velocity_servo')
        self.assertEqual(row['source'], 'SIMULATION_GROUND_TRUTH')
        self.assertAlmostEqual(row['object_in_tcp'][0], 0.1)

    def test_release_is_paired_and_stops_sampling(self):
        self.r.on_carry(True, 'session-1', T0)
        self.r.tick(T0 + PERIOD)
        self.r.on_carry(False, 'session-1', T0 + 2 * PERIOD)
        before = len(self.r.rows)
        self.r.tick(T0 + 10 * PERIOD)
        self.assertEqual([row['event'] for row in self.r.rows],
                         ['engage', 'carry', 'release'])
        self.assertEqual(len(self.r.rows), before)
        # the release row keeps the session it closes, so the pair is explicit
        self.assertEqual(self.r.rows[-1]['carry_session'], 'session-1')

    def test_sampling_respects_the_period(self):
        self.r.on_carry(True, 'session-1', T0)
        self.r.tick(T0 + PERIOD // 2)
        self.assertEqual([row['event'] for row in self.r.rows], ['engage'])
        self.r.tick(T0 + PERIOD)
        self.assertEqual([row['event'] for row in self.r.rows], ['engage', 'carry'])

    def test_identical_revision_is_not_written_twice(self):
        self.r.on_carry(True, 'session-1', T0)
        self.r.tick(T0 + PERIOD)
        self.r.tick(T0 + 2 * PERIOD)
        carries = [row for row in self.r.rows if row['event'] == 'carry']
        self.assertEqual(len(carries), 1)

    def test_new_revision_is_sampled(self):
        self.r.on_carry(True, 'session-1', T0)
        self.r.tick(T0 + PERIOD)
        self.r.on_world(snapshot(revision=2))
        self.r.tick(T0 + 2 * PERIOD)
        carries = [row for row in self.r.rows if row['event'] == 'carry']
        self.assertEqual([row['world_revision'] for row in carries], [1, 2])

    def test_object_follows_the_carry_state(self):
        r = rec.CarryOffsetRecorder('target_box_a')
        r.on_world(snapshot_with(['target_box_a', 'target_box_b']))
        r.on_carry(True, 'target_box_b', T0)
        self.assertEqual(r.object_name, 'target_box_b')
        self.assertEqual(r.rows[0]['object'], 'target_box_b')

    def test_grasp_event_fires_once_after_settle(self):
        r = rec.CarryOffsetRecorder('target_box_a', settle_s=0.1)
        r.on_world(snapshot(revision=2))
        r.on_carry(True, 'target_box_a', T0)

        r.tick(T0 + 60_000_000)
        self.assertNotIn('grasp', [row['event'] for row in r.rows])

        r.tick(T0 + 120_000_000)
        events = [row['event'] for row in r.rows]
        self.assertEqual(events.count('grasp'), 1)
        self.assertGreater(events.index('grasp'), events.index('engage'))

        r.tick(T0 + 200_000_000)
        self.assertEqual([row['event'] for row in r.rows].count('grasp'), 1)


class SkipTest(unittest.TestCase):
    """Unusable snapshots must be recorded as skips, never as zero offsets."""

    def setUp(self):
        self.r = rec.CarryOffsetRecorder('target_box_a', max_age_s=0.5)

    def test_unavailable_object_is_a_skip(self):
        self.r.on_world(snapshot(available=False))
        self.r.on_carry(True, 'session-1', T0)
        self.assertEqual(self.r.rows, [])
        self.assertEqual(self.r.skips[0]['event'], 'engage')
        self.assertIn('unavailable', self.r.skips[0]['reason'])

    def test_stale_sample_is_a_skip(self):
        self.r.on_world(snapshot(age=0.8))
        self.r.on_carry(True, 'session-1', T0)
        self.assertEqual(self.r.rows, [])
        self.assertIn('stale', self.r.skips[0]['reason'])

    def test_missing_end_effector_pose_is_a_skip(self):
        snap = snapshot()
        snap['robot']['ee_pose'] = None
        self.r.on_world(snap)
        self.r.on_carry(True, 'session-1', T0)
        self.assertEqual(self.r.rows, [])
        self.assertIn('end-effector', self.r.skips[0]['reason'])

    def test_missing_object_is_a_skip(self):
        self.r.on_world(dict(revision=1, source='SIMULATION_GROUND_TRUTH',
                             objects={}, robot={'ee_pose': ((0, 0, 0), IDENTITY)}))
        self.r.on_carry(True, 'session-1', T0)
        self.assertIn('absent', self.r.skips[0]['reason'])

    def test_skips_do_not_block_later_samples(self):
        self.r.on_world(snapshot(available=False))
        self.r.on_carry(True, 'session-1', T0)
        self.r.on_world(snapshot(revision=2, available=True))
        self.r.tick(T0 + PERIOD)
        self.assertEqual([row['event'] for row in self.r.rows], ['carry'])
        self.assertEqual(self.r.rows[0]['world_revision'], 2)


if __name__ == '__main__':
    unittest.main()
