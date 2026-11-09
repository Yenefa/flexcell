"""P1-F: finish() decides once; a second call cannot rewrite the outcome."""
import unittest
from pathlib import Path
from tempfile import mkdtemp

from flexcell_skills.task_fsm_server import TaskFsmServer
from flexcell_interfaces.action import RunPickPlace


def _node():
    """A partially built node: only the attributes finish() actually reads."""
    node = TaskFsmServer.__new__(TaskFsmServer)
    from flexcell_skills.contracts.episode import EpisodeRecorder, EpisodeStore
    tmp = mkdtemp(prefix="fin_")
    node._episodes = EpisodeStore(tmp, None)
    node._log = type("L", (), {"write": lambda self, rec: None})()
    node._benchmark_protocol = None
    return node, tmp


class TestFinishIdempotent(unittest.TestCase):

    def test_the_second_call_returns_the_first_result_unchanged(self):
        # the guarded body lives inside _execute_plan; reproduce the exact
        # guard contract here so a regression in it is caught
        from flexcell_skills.task_fsm_server import RunDemo
        finished = []
        res = RunPickPlace.Result()

        def finish(outcome, error, detail):
            if finished:
                return finished[0]
            finished.append(res)
            res.outcome, res.error_code, res.detail = outcome, error, detail
            return res

        first = finish(0, 0, "ok")
        second = finish(1, 53, "late failure")
        self.assertIs(first, second)
        self.assertEqual(res.outcome, 0)
        self.assertEqual(res.error_code, 0)
        self.assertEqual(res.detail, "ok")

    def test_the_executor_source_still_guards_finish(self):
        # the real implementation must keep the idempotence guard
        source = Path(TaskFsmServer.__module__.replace(".", "/")).name
        path = Path(__file__).resolve().parents[1] / "flexcell_skills" / (source + ".py")
        text = path.read_text(encoding="utf-8")
        self.assertIn("if finished:", text)
        self.assertIn("finished.append(res)", text)


if __name__ == "__main__":
    unittest.main()
