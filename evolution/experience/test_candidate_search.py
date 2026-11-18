#!/usr/bin/env python3
"""Tests for the candidate search: feasibility first, cost only among the feasible.

WHY THESE CASES
    A search that always returns its first candidate looks like a search and is not one.
    These tests drive it through states where it must reject, must refuse, and must not
    let a cheap-but-unsafe candidate win.
"""
import json
import os
import sys

import pytest

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

# NOT "select": that name shadows a stdlib module, and the shadowed import silently
# returned the stdlib one, so every test failed with "module 'select' has no attribute
# 'load_plans'". The rename is the fix.
import candidate_search as sel  # noqa: E402


def plan_at(sep, x=0.12, n=2, avoid=((0.22, 0.0), (0.20, -0.18))):
    stages = [{"stage_id": "s%d" % i, "object_name": "o%d" % i,
               "place_pose": [x - sep / 2.0 + i * sep, -0.15, 0.0175]}
              for i in range(n)]
    return {"stages": stages,
            "initial_objects": [{"object_name": "b%d" % i, "position": [a[0], a[1], 0.0]}
                                for i, a in enumerate(avoid)]}


# ---------------------------------------------------------------- evaluation

def test_evaluate_counts_a_fix():
    row = sel.evaluate("x", sel._respread(0.090, 0.120),
                       [{"path": "p", "plan": plan_at(0.056), "sep": 0.056,
                         "avoid": [[0.22, 0.0], [0.20, -0.18]]}])
    assert row["fixed"] == 1 and row["plans"] == 1
    assert row["clearance_violations"] == 0
    assert row["mean_displacement_m"] > 0


def test_a_refusal_counts_as_a_plan_not_fixed_not_as_an_error():
    def always_refuses(plan):
        raise ValueError("cannot place that")
    row = sel.evaluate("x", always_refuses,
                       [{"path": "p", "plan": plan_at(0.056), "sep": 0.056,
                         "avoid": []}])
    assert row["refused"] == 1 and row["fixed"] == 0


def test_a_candidate_that_touches_nothing_is_not_admissible():
    row = sel.evaluate("x", lambda p: [dict(s, place_pose=list(s["place_pose"]))
                                       for s in p["stages"]],
                       [{"path": "p", "plan": plan_at(0.056), "sep": 0.056,
                         "avoid": []}])
    assert row["fixed"] == 0 and row["untouched"] == 1
    ok, why = sel.admissible(row)
    assert not ok and "fixes 0 of 1" in why


def test_a_candidate_that_makes_separation_worse_is_not_admissible():
    row = {"plans": 1, "fixed": 1, "worse": 1, "clearance_violations": 0}
    ok, why = sel.admissible(row)
    assert not ok and "LESS separation" in why


def test_a_candidate_that_breaks_clearance_is_not_admissible():
    row = {"plans": 1, "fixed": 1, "worse": 0, "clearance_violations": 1}
    ok, why = sel.admissible(row)
    assert not ok and "clearance" in why


def test_an_empty_archive_is_refused_not_scored():
    ok, why = sel.admissible({"plans": 0, "fixed": 0, "worse": 0,
                              "clearance_violations": 0})
    assert not ok and "no plans" in why


# ---------------------------------------------------------------- the selection

def test_the_search_returns_the_cheapest_admissible_candidate():
    selection, board = sel.search()
    assert selection is not None
    admissible = [r for r in board if r["admissible"]]
    assert admissible
    assert selection["mean_displacement_m"] == min(
        r["mean_displacement_m"] for r in admissible)


def test_the_cheap_but_unsafe_candidate_loses_and_says_why():
    """minimal_move is cheaper on the two-stage case and must still lose on clearance."""
    selection, board = sel.search()
    cheap = next(r for r in board if r["candidate"].startswith("minimal_move"))
    assert cheap["admissible"] is False
    assert cheap["clearance_violations"] > 0
    assert "clearance" in cheap["why"]
    assert selection["candidate"] != cheap["candidate"]


def test_the_board_keeps_every_candidate_including_the_rejected_ones():
    """A board that omits the losers cannot show that anything was compared."""
    _, board = sel.search()
    assert len(board) == len(sel.CANDIDATES)
    assert any(not r["admissible"] for r in board)
    for row in board:
        assert "why" in row and row["why"]


def test_the_search_refuses_rather_than_falling_back(monkeypatch):
    """No admissible candidate must yield NO selection, not the incumbent."""
    bad = {"plans": 5, "fixed": 0, "worse": 0, "clearance_violations": 0,
           "refused": 5, "untouched": 5, "mean_displacement_m": None}
    monkeypatch.setattr(sel, "evaluate", lambda name, run, plans: dict(bad))
    selection, board = sel.search(plans=[{"path": "p", "plan": plan_at(0.056),
                                          "sep": 0.056, "avoid": []}])
    assert selection is None
    assert all(not r["admissible"] for r in board)


def test_load_plans_excludes_plans_already_at_the_contract():
    """Already-conforming plans are the control group; mixing them in inflates any score."""
    plans = sel.load_plans()
    assert plans, "no below-contract plans found in the archive"
    for row in plans:
        assert row["sep"] < sel.SPREAD_CONTRACT_M - 1e-9
