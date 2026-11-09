"""P1-F: episode and log integrity - no duplicate writes, no fake SUCCESS."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from flexcell_skills.contracts.episode import EpisodeStore, serialize_episode


class _Logger:
    def __init__(self):
        self.errors = []

    def error(self, message):
        self.errors.append(message)


def _record(**over):
    record = {"scenario_id": "s1", "run_id": "r1", "final_state": {"outcome": "0"}}
    record.update(over)
    return record


class TestEpisodeStore(unittest.TestCase):

    def test_a_record_is_written_as_utf8_and_reads_back_identically(self):
        tmp = tempfile.mkdtemp(prefix="ep_")
        logger = _Logger()
        store = EpisodeStore(tmp, logger)
        record = _record(final_state={"detail": "place 失败 · échec · 0.009m"})
        path = store.write(record)
        self.assertIsNotNone(path, logger.errors)
        text = Path(path).read_text(encoding="utf-8")
        self.assertEqual(json.loads(text), record)
        self.assertIn("失败", text)

    def test_no_temporary_file_is_left_behind(self):
        tmp = tempfile.mkdtemp(prefix="ep_")
        store = EpisodeStore(tmp, _Logger())
        store.write(_record())
        leftovers = [p for p in os.listdir(tmp) if ".tmp" in p]
        self.assertEqual(leftovers, [])

    def test_two_different_runs_do_not_overwrite_each_other(self):
        tmp = tempfile.mkdtemp(prefix="ep_")
        store = EpisodeStore(tmp, _Logger())
        first = store.write(_record(run_id="r1"))
        second = store.write(_record(run_id="r2"))
        self.assertNotEqual(first, second)
        self.assertEqual(json.loads(Path(first).read_text(encoding="utf-8"))["run_id"], "r1")
        self.assertEqual(json.loads(Path(second).read_text(encoding="utf-8"))["run_id"], "r2")

    def test_a_serialization_failure_is_reported_and_returns_none(self):
        tmp = tempfile.mkdtemp(prefix="ep_")
        logger = _Logger()
        store = EpisodeStore(tmp, logger)
        path = store.write({"scenario_id": "s1", "run_id": "r1",
                            "final_state": {"bad": float("nan")}})
        self.assertIsNone(path)
        self.assertTrue(logger.errors)
        self.assertEqual([p for p in os.listdir(tmp) if ".tmp" in p], [])

    def test_an_unwritable_directory_does_not_raise(self):
        logger = _Logger()
        store = EpisodeStore("/proc/definitely/not/writable", logger)
        self.assertIsNone(store.write(_record()))
        self.assertTrue(logger.errors)

    def test_serialization_is_deterministic(self):
        first = serialize_episode(_record(final_state={"b": 1, "a": 2}))
        second = serialize_episode(_record(final_state={"a": 2, "b": 1}))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
