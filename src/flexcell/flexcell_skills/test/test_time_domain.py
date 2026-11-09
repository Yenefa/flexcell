"""P2-D: a message that never arrived is infinitely old, not fresh."""
import time
import unittest

from flexcell_skills.move_to_pose_server import MoveToPoseServer


class _Fake:
    """A MoveToPoseServer with only the joint-state attributes under test."""

    _joint_state = MoveToPoseServer._joint_state

    def __init__(self):
        self._js = None
        self._js_monotonic = None


class TestJointStateFreshness(unittest.TestCase):

    def test_a_never_received_state_has_no_age(self):
        node = _Fake()
        js, age = node._joint_state()
        self.assertIsNone(js)
        self.assertIsNone(age)

    def test_a_received_state_reports_a_growing_monotonic_age(self):
        node = _Fake()
        node._js = object()
        node._js_monotonic = time.monotonic()
        _, first = node._joint_state()
        time.sleep(0.05)
        node._js_monotonic = time.monotonic() - 0.05
        _, second = node._joint_state()
        self.assertGreater(first, 0.0)
        self.assertGreaterEqual(second, 0.05)

    def test_no_numeric_sentinel_can_make_a_missing_state_look_fresh(self):
        # the defect: 0.0 compared against time.monotonic() reads as
        # "time since boot", which is small on a freshly started host
        node = _Fake()
        node._js_monotonic = 0.0
        js, age = node._joint_state()
        self.assertIsNone(js, "a state that never arrived must not be reported")
        self.assertIsNone(age)

    def test_the_source_no_longer_uses_a_numeric_sentinel(self):
        import inspect
        source = inspect.getsource(MoveToPoseServer)
        self.assertNotIn("_js_wall", source)
        self.assertIn("_js_monotonic", source)


class TestEpisodeClockLabel(unittest.TestCase):

    def test_the_episode_timestamps_declare_their_clock_domain(self):
        import inspect
        from flexcell_skills.contracts import episode
        source = inspect.getsource(episode)
        self.assertIn('"clock": "wall_unix_seconds"', source)


if __name__ == "__main__":
    unittest.main()
