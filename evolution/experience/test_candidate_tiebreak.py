#!/usr/bin/env python3
# "Cost-minimising search" must not resolve a tie by dict insertion order. On this board
# the incumbent and the tighter-clustering candidate cost exactly the same; the choice must
# be an explicit, auditable principle, not an accident of how CANDIDATES was written.
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import candidate_search  # noqa: E402


def _board_has_cost_tie():
    sel, board = candidate_search.search()
    ties = [r for r in board if r.get("admissible")
            and r.get("mean_displacement_m") == sel.get("mean_displacement_m")]
    return len(ties) > 1, ties


def test_cost_minimisation_has_explicit_tie_break():
    sel, _ = candidate_search.search()
    assert sel is not None
    has_tie, ties = _board_has_cost_tie()
    if has_tie:
        assert "cost_ties" in sel, "a tie must be recorded, not resolved silently"
        assert len(sel["cost_ties"]) > 1
        assert "incumbent" in sel["tie_break"]


def test_tie_break_does_not_depend_on_insertion_order(monkeypatch):
    """Reordering CANDIDATES must not change the chosen parameter when costs tie."""
    original = dict(candidate_search.CANDIDATES)
    sel_before, _ = candidate_search.search()
    # put the incumbent LAST so sort stability alone would choose the other tied candidate
    items = list(original.items())
    reordered = dict(items[1:] + items[:1])
    monkeypatch.setattr(candidate_search, "CANDIDATES", reordered)
    sel_after, _ = candidate_search.search()
    assert sel_after["candidate"] == sel_before["candidate"], (
        "tie-break is order-dependent: %s -> %s"
        % (sel_before["candidate"], sel_after["candidate"]))


def test_a_rejected_candidate_is_kept_with_its_reason():
    """DGM failure branches: a candidate that broke the contract stays on the board."""
    _, board = candidate_search.search()
    rejected = [r for r in board if not r["admissible"]]
    assert rejected
    assert all(r.get("why") for r in rejected), "a rejection with no reason is a silent loss"
