"""The agent must reach files through the same category gate as the tool facade.

MEASURED 2026-11-17 (review): read_file, search and edit_file passed the literal
"candidate_source" to the boundary. The no-feedback condition therefore read
telemetry/execution.log, saw OBJECT_NOT_REGISTERED and expected_objects, and the
record still claimed feedback_source=none. The gate was bypassed by the caller,
not by the boundary.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
for path in (str(HERE), str(HERE.parents[1]),
             str(HERE.parents[1] / "benchmark" / "repair_eval" / "contracts")):
    if path not in sys.path:
        sys.path.insert(0, path)

import budget as B                                  # noqa: E402
import instances as I                               # noqa: E402
from agent import RepairAgent                       # noqa: E402
from benchmark.repair_eval import visibility as vis  # noqa: E402

SECRET = '{"code": "OBJECT_NOT_REGISTERED", "expected_objects": ["target_box_a", "target_box_b"]}'


class Scripted:
    def __init__(self, actions):
        self.actions = list(actions)
        self.calls = 0
        self.seen = []

    def chat(self, messages, **kwargs):
        self.calls += 1
        self.seen.append(messages)
        acts = self.actions[self.calls - 1] if self.calls - 1 < len(self.actions) else []
        return {"text": json.dumps({"actions": acts, "claim_success": True,
                                    "done": not acts}),
                "usage": {"total_tokens": 0, "split_available": False}}


def _run(condition, actions):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        candidate = I.materialize("DEF-F1-REG", tmp / "candidate", "v2")
        (candidate / "telemetry").mkdir(exist_ok=True)
        (candidate / "telemetry" / "execution.log").write_text(SECRET, encoding="utf-8")
        verdict = tmp / "verdict"; verdict.mkdir()
        hidden = tmp / "hidden"; hidden.mkdir()
        policy = vis.load_policy(Path(HERE.parents[1]) / "benchmark" / "repair_eval"
                                 / "visibility_policy.json")
        boundary = vis.RunBoundary(policy, tmp, candidate, verdict, hidden,
                                   condition=condition, mismatch_dir=None)
        transport = Scripted(actions)
        ledger = B.Ledger(transport, max_interactions=4)
        agent = RepairAgent(ledger, boundary, "fix it", ["config/"])
        agent.step()
        return transport.seen[-1]


def _told(messages):
    return json.dumps(messages, ensure_ascii=False)


def test_the_no_feedback_condition_cannot_read_telemetry_through_the_agent():
    messages = _run("A_STATIC", [[{"read_file": ["telemetry/execution.log"]}]])
    assert "expected_objects" not in _told(messages), "A read the feedback payload"


def test_search_cannot_used_to_scrape_the_same_file():
    messages = _run("A_STATIC", [[{"search": ["telemetry/execution.log", "OBJECT"]}]])
    assert "OBJECT_NOT_REGISTERED" not in _told(messages)


def test_a_real_feedback_condition_can_still_read_it():
    """The fix must not close the channel for the conditions allowed to use it."""
    messages = _run("B_REAL_FEEDBACK", [[{"read_file": ["telemetry/execution.log"]}]])
    assert "expected_objects" in _told(messages)


def test_the_agent_asks_for_the_category_the_path_deserves():
    """The caller, not the boundary, must classify.

    The boundary now refuses a telemetry read under A whatever category it is
    given, so the earlier tests pass even with the caller bug restored. This one
    looks at what the caller asked for: under B the read must be recorded as
    execution_feedback, because a hardcoded candidate_source would be the same
    mistake with a different outcome.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        candidate = I.materialize("DEF-F1-REG", tmp / "candidate", "v2")
        (candidate / "telemetry").mkdir(exist_ok=True)
        (candidate / "telemetry" / "execution.log").write_text(SECRET, encoding="utf-8")
        verdict = tmp / "verdict"; verdict.mkdir()
        hidden = tmp / "hidden"; hidden.mkdir()
        policy = vis.load_policy(Path(HERE.parents[1]) / "benchmark" / "repair_eval"
                                 / "visibility_policy.json")
        boundary = vis.RunBoundary(policy, tmp, candidate, verdict, hidden,
                                   condition="B_REAL_FEEDBACK", mismatch_dir=None)
        transport = Scripted([[{"read_file": ["telemetry/execution.log"]}]])
        ledger = B.Ledger(transport, max_interactions=4)
        agent = RepairAgent(ledger, boundary, "fix it", ["config/"])
        agent.step()
    # The initial feedback read is itself category execution_feedback, so the set
    # of categories is not a discriminator. Look at the attempt made for this path.
    mine = [a for a in boundary.attempts
            if a.get("path") == "telemetry/execution.log"
            and str(a.get("operation", "")).startswith("read")]
    assert mine, "no attempt was recorded for the path the agent read"
    assert all(a.get("category") == "execution_feedback" for a in mine), \
        "the agent named the path %r instead of classifying it" % (mine,)
