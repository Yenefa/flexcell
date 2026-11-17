"""Tests for the 5.1 budget cap and the repair loop that spends it.

These are the first tests in the repository that execute the protocol's budget
rules. Before this file, "6 interactions and 20,000 tokens, exhaustion is not
success" was a sentence in a document with no code behind it.
"""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (str(HERE), str(ROOT), str(ROOT / "benchmark" / "repair_eval" / "contracts")):
    if path not in sys.path:
        sys.path.insert(0, path)

import budget as B           # noqa: E402
from benchmark.repair_eval import visibility as vis  # noqa: E402
from agent import RepairAgent, _parse  # noqa: E402


class FakeTransport:
    """Counts its own calls so a test can prove one was never made."""

    def __init__(self, replies=None, tokens=100, prompt_tokens=80):
        self.replies = list(replies or [])
        self.tokens = tokens
        self.prompt_tokens = prompt_tokens
        self.calls = 0
        self.seen = []

    def chat(self, messages, **kwargs):
        self.calls += 1
        self.seen.append(messages)
        if self.replies:
            text = self.replies.pop(0)
        else:
            text = '{"actions": [], "claim_success": false, "done": false}'
        return {"text": text,
                "usage": {"prompt_tokens": self.prompt_tokens,
                          "completion_tokens": self.tokens}}


def ledger_with(**kwargs):
    transport = kwargs.pop("transport", None) or FakeTransport()
    return B.Ledger(transport, **kwargs), transport


# --------------------------------------------------------------- the cap
def test_six_interactions_are_allowed_and_the_seventh_is_never_sent():
    ledger, transport = ledger_with(max_interactions=6, max_tokens=10 ** 6)
    for _ in range(6):
        ledger.chat([{"role": "user", "content": "hi"}])
    assert transport.calls == 6
    with pytest.raises(B.BudgetExhausted) as exc:
        ledger.chat([{"role": "user", "content": "one more"}])
    # the cap is checked before the call, so nothing was spent on it
    assert transport.calls == 6
    assert exc.value.which == "interactions"


def test_a_closed_ledger_refuses_every_later_call_without_reaching_the_transport():
    ledger, transport = ledger_with(max_interactions=1, max_tokens=10 ** 6)
    ledger.chat([])
    for _ in range(3):
        with pytest.raises(B.BudgetExhausted):
            ledger.chat([])
    # 5.1 forbids "one more try": no topping up, and no further spend
    assert transport.calls == 1


def test_the_token_cap_stops_the_record_and_keeps_the_cost_that_was_spent():
    ledger, transport = ledger_with(max_interactions=6, max_tokens=250)
    # 80 prompt + 100 completion = 180 per call, so the second call crosses 250
    ledger.chat([])
    with pytest.raises(B.BudgetExhausted) as exc:
        ledger.chat([])
    assert exc.value.which == "tokens"
    assert ledger.tokens_total == 360      # both calls counted, not truncated
    assert ledger.interactions_used == 2


def test_tokens_already_at_the_cap_refuse_before_calling():
    ledger, transport = ledger_with(max_interactions=6, max_tokens=180)
    ledger.chat([])                        # lands exactly on the cap
    calls_before = transport.calls
    with pytest.raises(B.BudgetExhausted):
        ledger.chat([])
    assert transport.calls == calls_before


# ------------------------------------------------------------ accounting
def test_the_account_carries_every_field_5_2_requires():
    ledger, _ = ledger_with()
    ledger.chat([])
    ledger.count_execution()
    ledger.finish()
    account = ledger.account()
    for field in ("interactions_used", "interactions_cap", "tokens_in",
                  "tokens_out", "tokens_total", "candidate_executions",
                  "wall_clock_s", "budget_exhausted_at"):
        assert field in account, field
    assert account["interactions_used"] == 1
    assert account["tokens_in"] == 80
    assert account["tokens_out"] == 100
    assert account["tokens_total"] == 180
    assert account["candidate_executions"] == 1
    assert account["budget_exhausted_at"] is None


@pytest.mark.parametrize("which,expected", [
    ("interactions", "interaction:7"),
    ("tokens", "token:20013"),
    ("candidate_executions", "candidate_executions:7"),
])
def test_the_exhaustion_position_uses_the_documented_string_form(which, expected):
    exc = B.BudgetExhausted(which, 7, 20013)
    assert exc.position_text() == expected


def test_a_record_counts_at_most_one_final_scene():
    ledger, _ = ledger_with()
    assert ledger.account()["final_scenes"] == 0
    ledger.count_final_scene()
    assert ledger.account()["final_scenes"] == 1
    with pytest.raises(B.BudgetExhausted):
        ledger.count_final_scene()


def test_an_exhausted_account_records_where_it_stopped():
    ledger, _ = ledger_with(max_interactions=2, max_tokens=10 ** 6)
    ledger.chat([])
    ledger.chat([])
    with pytest.raises(B.BudgetExhausted):
        ledger.chat([])
    # DATA_DICTIONARY 3.4 fixes this as a string, not a structure
    assert ledger.account()["budget_exhausted_at"] == "interaction:2"


def test_closing_for_one_reason_blocks_every_other_kind_of_spend():
    """A ledger shut by one limit must not be re-opened by another's headroom.

    Without this case the "no topping up" rule is only reached through the
    interaction check, which independently refuses anyway - so deleting the
    closed-ledger guard would not fail any test. Measured: it did not.
    """
    ledger, transport = ledger_with(max_candidate_executions=1)
    ledger.count_execution()
    with pytest.raises(B.BudgetExhausted):
        ledger.count_execution()
    # interactions and tokens are both untouched, and it must not matter
    assert ledger.interactions_used == 0
    assert ledger.tokens_total == 0
    with pytest.raises(B.BudgetExhausted) as exc:
        ledger.chat([{"role": "user", "content": "hi"}])
    assert exc.value.which == "candidate_executions"
    assert transport.calls == 0


def test_the_candidate_execution_cap_closes_the_ledger_too():
    ledger, transport = ledger_with(max_candidate_executions=1)
    ledger.count_execution()
    with pytest.raises(B.BudgetExhausted) as exc:
        ledger.count_execution()
    assert exc.value.which == "candidate_executions"
    assert transport.calls == 0


# ------------------------------------------------------- the terminal rule
def test_exhaustion_cannot_be_upgraded_to_success_by_a_late_claim():
    ledger, _ = ledger_with(max_interactions=1, max_tokens=10 ** 6)
    ledger.chat([])
    with pytest.raises(B.BudgetExhausted):
        ledger.chat([])
    # the agent said it succeeded, but 5.1 says an exhausted record is not a
    # success. Exhaustion wins over the claim.
    assert ledger.terminal_state(claimed_success=True) == B.BUDGET_EXHAUSTED


def test_a_run_that_never_claimed_success_is_not_done():
    ledger, _ = ledger_with()
    ledger.chat([])
    assert ledger.terminal_state(claimed_success=False) == B.INVALID
    assert ledger.terminal_state(claimed_success=True) == B.DONE


# ------------------------------------------------------------- the agent
def _boundary(tmp_path, condition, feedback_text=None):
    policy = vis.load_policy(ROOT / "benchmark" / "repair_eval" / "visibility_policy.json")
    cand = tmp_path / "candidate"
    (cand / "skill").mkdir(parents=True)
    (cand / "task.md").write_text("Fix the registry.\n")
    (cand / "gate").mkdir()
    (cand / "gate" / "acceptance.py").write_text("PASS_IF=0.02\n")
    (cand / "skill" / "registry.py").write_text("broken\n")
    # B reads this run's telemetry from inside the candidate, which is where the
    # execution subprocess writes it and which the agent may not write to.
    (cand / "telemetry").mkdir()
    (cand / "telemetry" / "execution.log").write_text(
        feedback_text or "REAL FAILURE: registry returned []\n")
    own = tmp_path / "own"
    own.mkdir()
    (own / "verdict.json").write_text('{"passed": false}\n')
    (tmp_path / "hidden").mkdir()
    donor = tmp_path / "donor" / "telemetry"
    donor.mkdir(parents=True)
    (donor / "execution.log").write_text("DONOR FAILURE: other run\n")
    (tmp_path / "donor" / "verdict.json").write_text('{"passed": false}\n')
    return vis.RunBoundary(policy, tmp_path, cand, tmp_path / "own",
                           tmp_path / "hidden", condition=condition,
                           mismatch_dir=tmp_path / "donor")


def test_condition_a_never_puts_feedback_in_the_prompt(tmp_path):
    boundary = _boundary(tmp_path, "A_STATIC")
    ledger, transport = ledger_with()
    agent = RepairAgent(ledger, boundary, "Fix the registry.", ["skill/"])
    agent.run()
    sent = transport.seen[0]
    joined = " ".join(m["content"] for m in sent)
    assert "EXECUTION FEEDBACK" not in joined
    assert "REAL FAILURE" not in joined


def test_condition_b_puts_this_runs_feedback_in_the_prompt(tmp_path):
    boundary = _boundary(tmp_path, "B_REAL_FEEDBACK")
    ledger, transport = ledger_with()
    agent = RepairAgent(ledger, boundary, "Fix the registry.", ["skill/"])
    agent.run()
    joined = " ".join(m["content"] for m in transport.seen[0])
    assert "EXECUTION FEEDBACK" in joined


def test_the_agent_cannot_write_a_protected_file(tmp_path):
    boundary = _boundary(tmp_path, "B_REAL_FEEDBACK")
    transport = FakeTransport(replies=[
        '{"actions": [{"write_file": ["task.md", "rewritten"]}], '
        '"claim_success": true, "done": true}'])
    ledger = B.Ledger(transport)
    agent = RepairAgent(ledger, boundary, "Fix the registry.", ["skill/"])
    with pytest.raises(vis.BoundaryError):
        agent.run()


def test_the_agent_cannot_read_the_evaluator_through_the_boundary(tmp_path):
    boundary = _boundary(tmp_path, "B_REAL_FEEDBACK")
    with pytest.raises(vis.BoundaryError):
        boundary.read_text("gate/acceptance.py", "static_input")


def test_an_unparseable_reply_costs_an_interaction_and_does_not_claim_success(tmp_path):
    boundary = _boundary(tmp_path, "B_REAL_FEEDBACK")
    transport = FakeTransport(replies=["I think it is fixed!", '{"actions": [], "claim_success": true, "done": true}'])
    ledger = B.Ledger(transport)
    result = RepairAgent(ledger, boundary, "Fix.", ["skill/"]).run()
    assert transport.calls == 2
    assert result["account"]["interactions_used"] == 2


def test_the_loop_stops_at_the_cap_and_reports_exhaustion(tmp_path):
    boundary = _boundary(tmp_path, "B_REAL_FEEDBACK")
    transport = FakeTransport()          # always "not done"
    ledger = B.Ledger(transport, max_interactions=3, max_tokens=10 ** 6)
    result = RepairAgent(ledger, boundary, "Fix.", ["skill/"]).run()
    assert transport.calls == 3
    assert result["terminal_state"] == B.BUDGET_EXHAUSTED
    assert result["account"]["budget_exhausted_at"] == "interaction:3"


# ------------------------------------------------------------- json parsing
@pytest.mark.parametrize("text,expected", [
    ('{"done": true}', True),
    ('```json\n{"done": true}\n```', True),
    ('Sure! {"done": true} hope that helps', True),
    ("no json here", None),
    ("", None),
    (None, None),
    ('[1, 2, 3]', None),
])
def test_parse_tolerates_fences_and_prose_but_not_nonsense(text, expected):
    parsed = _parse(text)
    if expected is None:
        assert parsed is None
    else:
        assert isinstance(parsed, dict)
