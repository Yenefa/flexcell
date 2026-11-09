"""P2-A: budget lifecycle - void/release, settle anomalies, concurrency."""
import json
import tempfile
import threading
import unittest
from pathlib import Path

from flexcell_skills.inference_budget import BudgetExceeded, InferenceBudget


def _payload(max_tokens=64):
    return {"model": "deepseek-flash", "messages": [{"role": "user", "content": "hi"}],
            "thinking": {"type": "disabled"}, "max_tokens": max_tokens}


def _budget():
    return InferenceBudget(Path(tempfile.mkdtemp(prefix="budget_")) / "ledger.json")


def _state(budget):
    return json.loads(Path(budget.path).read_text())


class TestVoidRelease(unittest.TestCase):

    def test_void_releases_a_reservation_the_provider_never_saw(self):
        budget = _budget()
        call = budget.reserve("https://api.deepseek.com/chat/completions", _payload())
        self.assertGreater(_state(budget)["committed_upper_bound_microyuan"], 0)
        out = budget.void(call, "connection refused before send")
        self.assertEqual(out["status"], "RELEASED_NEVER_SENT")
        self.assertGreater(out["released_microyuan"], 0)
        self.assertEqual(_state(budget)["committed_upper_bound_microyuan"], 0)

    def test_void_requires_a_reason(self):
        budget = _budget()
        call = budget.reserve("https://api.deepseek.com/chat/completions", _payload())
        for bad in ("", "   ", None, 7):
            with self.subTest(reason=bad):
                with self.assertRaises(ValueError):
                    budget.void(call, bad)

    def test_void_is_a_no_op_on_an_already_settled_call(self):
        budget = _budget()
        call = budget.reserve("https://api.deepseek.com/chat/completions", _payload())
        budget.settle(call, {"usage": {"prompt_tokens": 5, "completion_tokens": 5}})
        before = _state(budget)["committed_upper_bound_microyuan"]
        out = budget.void(call, "late")
        self.assertEqual(out["released_microyuan"], 0)
        self.assertEqual(_state(budget)["committed_upper_bound_microyuan"], before)

    def test_release_is_the_documented_alias(self):
        budget = _budget()
        call = budget.reserve("https://api.deepseek.com/chat/completions", _payload())
        self.assertEqual(budget.release(call, "alias")["status"], "RELEASED_NEVER_SENT")

    def test_an_unknown_outcome_keeps_its_reservation(self):
        budget = _budget()
        call = budget.reserve("https://api.deepseek.com/chat/completions", _payload())
        before = _state(budget)["committed_upper_bound_microyuan"]
        # a response without usage is the unknown-outcome case
        budget.settle(call, {})
        self.assertEqual(_state(budget)["committed_upper_bound_microyuan"], before)


class TestSettleHardening(unittest.TestCase):

    def test_an_unknown_call_id_is_reported_not_raised(self):
        budget = _budget()
        out = budget.settle("nope", {"usage": {"prompt_tokens": 1, "completion_tokens": 1}})
        self.assertEqual(out["status"], "UNKNOWN_CALL_ID")

    def test_usage_above_the_reservation_keeps_the_whole_reservation(self):
        budget = _budget()
        call = budget.reserve("https://api.deepseek.com/chat/completions", _payload(64))
        reserved = _state(budget)["calls"][0]["reserved_microyuan"]
        out = budget.settle(call, {"usage": {"prompt_tokens": 10, "completion_tokens": 100000}})
        self.assertEqual(out["status"], "ANOMALY_USAGE_EXCEEDED_RESERVATION")
        state = _state(budget)
        self.assertEqual(state["committed_upper_bound_microyuan"], reserved)
        self.assertNotIn("settled_microyuan", state["calls"][0])

    def test_a_normal_settle_lowers_the_committed_amount(self):
        budget = _budget()
        call = budget.reserve("https://api.deepseek.com/chat/completions", _payload())
        reserved = _state(budget)["committed_upper_bound_microyuan"]
        budget.settle(call, {"usage": {"prompt_tokens": 5, "completion_tokens": 5}})
        self.assertLess(_state(budget)["committed_upper_bound_microyuan"], reserved)


class TestConcurrency(unittest.TestCase):

    def test_parallel_reservations_never_lose_a_call(self):
        budget = _budget()
        ids, errors = [], []
        lock = threading.Lock()

        def worker():
            try:
                call = budget.reserve(
                    "https://api.deepseek.com/chat/completions", _payload())
                with lock:
                    ids.append(call)
            except Exception as exc:  # pragma: no cover - failure path
                with lock:
                    errors.append(repr(exc))

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(ids), 8)
        self.assertEqual(len(set(ids)), 8)
        self.assertEqual(len(_state(budget)["calls"]), 8)

    def test_the_budget_cap_still_refuses_oversubscription(self):
        budget = _budget()
        payload = _payload(65536)
        with self.assertRaises(BudgetExceeded):
            for _ in range(100):
                budget.reserve("https://api.deepseek.com/chat/completions", payload)


if __name__ == "__main__":
    unittest.main()
