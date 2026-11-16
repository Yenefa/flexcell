"""The summary must not let the interaction cap pass for a stable measurement.

F2 condition A reported 6.00 interactions with sd 0.00 in the first real matrix.
That is the cap talking: all three slots sat on it. A table that prints the mean
without the count is worse than no table, because sd 0.00 reads as precision.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import summarise as S  # noqa: E402


def row(slot, condition, used, codes=(), terminal="UNKNOWN", tokens=100):
    return {"slot_id": slot, "condition": condition, "interactions_used": used,
            "gate_contract_codes": list(codes), "terminal_status": terminal,
            "tokens_total": tokens}


def test_a_cell_on_the_cap_is_labelled_as_the_cap():
    rows = [row("F2-A-r1", "A_STATIC", 6), row("F2-A-r2", "A_STATIC", 6),
            row("F2-A-r3", "A_STATIC", 6)]
    cells = S.summarise(rows, cap=6)
    cell = cells[("F2", "A_STATIC")]
    assert cell["at_cap"] == 3
    assert cell["all_censored"] is True
    assert "describes the cap" in S.render(cells)


def test_sitting_on_the_cap_counts_even_when_the_gate_passed():
    """UNKNOWN at the cap is still a slot that ran out of room, not one that finished."""
    rows = [row("F2-A-r1", "A_STATIC", 6), row("F2-A-r2", "A_STATIC", 5)]
    cell = S.summarise(rows, cap=6)[("F2", "A_STATIC")]
    assert cell["at_cap"] == 1
    assert cell["all_censored"] is False


def test_exhausted_is_counted_as_censored_without_the_cap():
    rows = [row("F1-A-r1", "A_STATIC", 4, terminal="BUDGET_EXHAUSTED")]
    cell = S.summarise(rows, cap=6)[("F1", "A_STATIC")]
    assert cell["censored"] == 1


def test_pass_counts_the_gate_and_not_the_terminal_state():
    rows = [row("F1-A-r1", "A_STATIC", 3),
            row("F1-A-r2", "A_STATIC", 3, codes=["CONFIG_SECTION_MISSING"],
                terminal="FAIL"),
            row("F1-A-r3", "A_STATIC", 6, terminal="BUDGET_EXHAUSTED")]
    cell = S.summarise(rows, cap=6)[("F1", "A_STATIC")]
    assert cell["gate_pass"] == 2, "an exhausted slot whose gate passed still counts"


def test_no_success_rate_is_printed():
    rows = [row("F1-A-r1", "A_STATIC", 3)]
    text = S.render(S.summarise(rows, cap=6))
    assert "success rate" in text.lower()
    assert "No success rate is printed" in text
    assert "%" not in text, "a percentage here would be a rate the rules forbid"
