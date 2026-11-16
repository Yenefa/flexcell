"""A targeted edit must be able to repair a file too large to rewrite.

Measured on 2026-11-17: given only write_file, the model replaced a 1578-line
node with an 18-line stub that contained the right mapping and nothing else. The
node was correct and useless. That is an interface result, not a capability one,
so the agent gained edit_file, and this test holds it to the two properties that
matter: a targeted edit repairs the instance, and an edit whose anchor does not
exist says so instead of silently doing nothing.
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

import instances as I                              # noqa: E402
import run_matrix_real as R                        # noqa: E402
import budget as B                                 # noqa: E402
from agent import RepairAgent                      # noqa: E402
from benchmark.repair_eval import visibility as vis  # noqa: E402


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


def _boundary(tmp, instance):
    candidate = I.materialize(instance, Path(tmp) / "candidate")
    verdict = Path(tmp) / "verdict"; verdict.mkdir()
    hidden = Path(tmp) / "hidden"; hidden.mkdir()
    policy = vis.load_policy(Path(HERE.parents[1]) / "benchmark" / "repair_eval"
                             / "visibility_policy.json")
    # the runner writes an initial feedback file before the first step; a
    # boundary with no feedback to read raises, which is not what this test is about
    (candidate / "telemetry").mkdir(exist_ok=True)
    (candidate / "telemetry" / "execution.log").write_text('{"code": "OBJECT_NOT_REGISTERED"}')
    return vis.RunBoundary(policy, Path(tmp), candidate, verdict, hidden,
                           condition="B_REAL_FEEDBACK", mismatch_dir=None), candidate


def _drive(tmp, instance, actions):
    boundary, candidate = _boundary(tmp, instance)
    transport = Scripted(actions)
    ledger = B.Ledger(transport, max_interactions=4)
    agent = RepairAgent(ledger, boundary, "fix it", [str(Path(I.editable_rel(instance)).parent) + "/"])
    agent.run()
    return candidate, transport


def test_a_targeted_edit_repairs_the_large_file():
    with tempfile.TemporaryDirectory() as tmp:
        candidate, _ = _drive(tmp, "DEF-F2-MAP", [[{
            "edit_file": ["src/task_fsm_server.py",
                          "((self._obj_a, 'zone_2'), (self._obj_b, 'zone_1'))",
                          "((self._obj_a, 'zone_1'), (self._obj_b, 'zone_2'))"]}]])
        ok, payload = I.check("DEF-F2-MAP", candidate)
        assert ok, payload
        written = (candidate / "src" / "task_fsm_server.py").read_text(encoding="utf-8")
        assert len(written.splitlines()) > 1000, "the node must survive the repair"


def test_an_edit_with_a_missing_anchor_is_reported_not_silently_ignored():
    with tempfile.TemporaryDirectory() as tmp:
        candidate, transport = _drive(tmp, "DEF-F2-MAP", [[{
            "edit_file": ["src/task_fsm_server.py", "text that is not there", "x"]}]])
        ok, _payload = I.check("DEF-F2-MAP", candidate)
        assert not ok, "an edit that matched nothing must not change the verdict"
        told = json.dumps(transport.seen[-1], ensure_ascii=False)
        assert "not found" in told, "the agent was not told its anchor did not match"


def test_the_prompt_offers_the_targeted_edit():
    with tempfile.TemporaryDirectory() as tmp:
        _candidate, transport = _drive(tmp, "DEF-F1-REG", [[]])
        prompt = json.dumps(transport.seen[0], ensure_ascii=False)
        assert "edit_file" in prompt and "write_file" in prompt


def test_the_agent_can_read_the_file_it_repairs():
    """Without this the only way to produce old_text is to guess it."""
    with tempfile.TemporaryDirectory() as tmp:
        candidate, transport = _drive(tmp, "DEF-F2-MAP", [[{
            "read_file": ["src/task_fsm_server.py"]}]])
        told = json.dumps(transport.seen[-1], ensure_ascii=False)
        assert "FILE src/task_fsm_server.py" in told
        assert "zone_2" in told, "the read did not return the file's content"
