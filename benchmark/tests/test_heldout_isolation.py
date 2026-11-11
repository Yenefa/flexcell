#!/usr/bin/env python3
"""Held-out isolation tests: the enforcement must be checkable, and must be able to fail.

WHY: the isolation was a documented promise for many rounds because nothing tested it.
A verifier that cannot fail is the same promise with extra steps, so these tests drive
the static check through BOTH states on a synthetic tree - locked, then world-readable -
and assert the verdict flips.

The live probes (uid 1001 denial, evaluator still grading) need sudo and a real checkout,
so they live in scripts/heldout_isolation.py verify and are exercised by the acceptance
batch, not by this offline suite. That split is deliberate: this suite must stay runnable
with no privilege, and must never pass by skipping.
"""
import json
import os
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import heldout_isolation as iso


def _make_tree(tmp_path, mode=0o755, file_mode=0o644):
    """A miniature checkout with all three locked prefixes populated."""
    for prefix in iso.LOCKED_PREFIXES:
        d = tmp_path / prefix
        d.mkdir(parents=True, exist_ok=True)
        (d / "task.json").write_text('{"task_id": "HO-test"}', encoding="utf-8")
        os.chmod(d / "task.json", file_mode)
        os.chmod(d, mode)
    return tmp_path


# --------------------------------------------------------------------- the static gate
def test_a_world_readable_tree_is_reported_as_unlocked(tmp_path):
    wt = _make_tree(tmp_path, 0o755, 0o644)
    violations = iso.static_check(wt, expect_owner=False)
    assert violations, "a 0755 tree must not pass the isolation check"
    assert any(v["why"] == "world-accessible" for v in violations)


def test_a_locked_tree_passes(tmp_path):
    wt = _make_tree(tmp_path, iso.DIR_MODE, iso.FILE_MODE)
    assert iso.static_check(wt, expect_owner=False) == []


def test_the_gate_can_flip_between_states(tmp_path):
    """The decisive property: same tree, two states, opposite verdicts."""
    wt = _make_tree(tmp_path, 0o755, 0o644)
    assert iso.static_check(wt, expect_owner=False), "unlocked state must fail"

    for prefix in iso.LOCKED_PREFIXES:
        d = wt / prefix
        os.chmod(d / "task.json", iso.FILE_MODE)
        os.chmod(d, iso.DIR_MODE)
    assert iso.static_check(wt, expect_owner=False) == [], "locked state must pass"


def test_a_group_writable_file_is_rejected(tmp_path):
    """The agent must not be able to WRITE its way around the lock either."""
    wt = _make_tree(tmp_path, iso.DIR_MODE, 0o660)
    violations = iso.static_check(wt, expect_owner=False)
    assert any(v["why"] == "group-writable" for v in violations), violations


def test_a_directory_without_group_traverse_is_rejected(tmp_path):
    """0700 root:root also locks the evaluator out - that is a failure, not a fix."""
    wt = _make_tree(tmp_path, 0o700, iso.FILE_MODE)
    violations = iso.static_check(wt, expect_owner=False)
    assert any(v["why"] == "no group traverse" for v in violations), violations


def test_ownership_is_checked_when_asked(tmp_path):
    """A tree the agent OWNS is not isolated: the owner can chmod it back.

    The expected owner is passed explicitly, so this asserts the rule itself and does
    not depend on whether pytest is running as ros or as root.
    """
    wt = _make_tree(tmp_path, iso.DIR_MODE, iso.FILE_MODE)
    violations = iso.static_check(wt, expect_owner=True, expected_uid=4242424,
                                  expected_gid=4242424)
    assert any(v["why"] == "not owned by root" for v in violations), violations
    assert any(v["why"].startswith("not group") for v in violations), violations


def test_a_correctly_owned_tree_passes_the_ownership_check(tmp_path):
    """Negative control for the test above: the rule must not fire on a clean tree."""
    import os as _os
    wt = _make_tree(tmp_path, iso.DIR_MODE, iso.FILE_MODE)
    st = _os.stat(wt / "benchmark" / "held_out")
    violations = iso.static_check(wt, expect_owner=True, expected_uid=st.st_uid,
                                  expected_gid=st.st_gid)
    assert violations == [], violations


# ----------------------------------------------------------- the oracle is part of the lock
def test_the_generators_directory_is_locked_because_it_is_the_oracle():
    """Sealing the answers is not enough if the function that produces them is readable.

    Measured leak: with benchmark/generators/ readable, uid 1001 recovered the sealed
    expected_goal for HO-fd5737f932db in under a second by brute-forcing the seed space.
    """
    assert "benchmark/generators" in iso.LOCKED_PREFIXES
    assert "benchmark/held_out" in iso.LOCKED_PREFIXES
    assert "benchmark/evaluators" in iso.LOCKED_PREFIXES


def test_the_train_split_is_not_locked():
    """The agent is SUPPOSED to read the train split; locking it would break the agent."""
    for prefix in iso.LOCKED_PREFIXES:
        assert not prefix.startswith(iso.CONTROL_PREFIX), prefix
        assert not iso.CONTROL_PREFIX.startswith(prefix), prefix


# ---------------------------------------------------------------- the staging escape hatch
def test_stage_public_refuses_a_task_carrying_answers(tmp_path):
    bad = tmp_path / "leaky.json"
    bad.write_text(json.dumps({"task_id": "HO-x", "instruction": "do it",
                               "expected_goal": {"placement": {"a": "zone_1"}}}),
                   encoding="utf-8")
    with pytest.raises(SystemExit):
        iso.stage_public(ROOT, bad, tmp_path / "run")


def test_stage_public_copies_a_clean_task_and_makes_it_agent_readable(tmp_path):
    good = tmp_path / "clean.json"
    good.write_text(json.dumps({"task_id": "HO-y", "instruction": "do it",
                                "objects": [], "zones": []}), encoding="utf-8")
    run = tmp_path / "run"
    assert iso.stage_public(ROOT, good, run) == 0
    staged = run / "public_task.json"
    assert staged.is_file()
    assert stat.S_IMODE(os.stat(staged).st_mode) & 0o004, "staged task must be readable"
    assert "expected_goal" not in json.loads(staged.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ honest residual risk
def test_residual_risks_are_named_and_never_claim_absolute_safety():
    """The mechanism is OS permissions. The verifier must say so, not sell certainty."""
    src = (ROOT / "scripts" / "heldout_isolation.py").read_text(encoding="utf-8")
    assert "kernel namespace" in src
    assert "WSL interop" in src
    # a verifier that reports "closed" for a known-open bypass is the bug we are fixing
    assert '"closed": False' in src


def test_the_verifier_reports_a_non_zero_exit_when_the_gate_fails(tmp_path, monkeypatch):
    """End-to-end: verify() on an unlocked tree must return 1, not 0.

    sudo is stubbed out so this runs offline. The static gate is the part under test;
    the live probes are skipped exactly as they are when sudo is unavailable.
    """
    wt = _make_tree(tmp_path, 0o755, 0o644)
    monkeypatch.setattr(iso, "_can_sudo", lambda: True)
    monkeypatch.setattr(iso, "probe_agent_blocked", lambda w: [])
    monkeypatch.setattr(iso, "probe_control_still_readable", lambda w: [])
    monkeypatch.setattr(iso, "probe_reconstruction", lambda w: [])
    monkeypatch.setattr(iso, "probe_sealed_blocked", lambda: [])
    monkeypatch.setattr(iso, "probe_evaluator_can_grade", lambda w: [])
    monkeypatch.setattr(iso, "measure_residual_risks", lambda w: [])
    monkeypatch.setattr(iso, "_emit", lambda *a, **k: None)
    assert iso.verify(wt, as_json=True, expect_owner=False) == 1


def test_verify_returns_zero_only_when_every_probe_passes(tmp_path, monkeypatch):
    wt = _make_tree(tmp_path, iso.DIR_MODE, iso.FILE_MODE)
    monkeypatch.setattr(iso, "_can_sudo", lambda: True)
    monkeypatch.setattr(iso, "probe_agent_blocked", lambda w: [{"probe": "x", "ok": True}])
    monkeypatch.setattr(iso, "probe_control_still_readable",
                        lambda w: [{"probe": "c", "ok": True}])
    monkeypatch.setattr(iso, "probe_reconstruction", lambda w: [{"probe": "r", "ok": True}])
    monkeypatch.setattr(iso, "probe_sealed_blocked", lambda: [{"probe": "s", "ok": True}])
    monkeypatch.setattr(iso, "probe_evaluator_can_grade",
                        lambda w: [{"probe": "e", "ok": True}])
    monkeypatch.setattr(iso, "measure_residual_risks", lambda w: [])
    monkeypatch.setattr(iso, "_emit", lambda *a, **k: None)
    # expect_owner=False: pytest's tmp_path belongs to the test user, not root. The
    # production call passes True - ownership is what stops the agent chmod-ing back.
    assert iso.verify(wt, as_json=True, expect_owner=False) == 0


def test_one_failing_probe_is_enough_to_fail_the_gate(tmp_path, monkeypatch):
    """The evaluator-side direction must be part of the gate, not advisory."""
    wt = _make_tree(tmp_path, iso.DIR_MODE, iso.FILE_MODE)
    monkeypatch.setattr(iso, "_can_sudo", lambda: True)
    monkeypatch.setattr(iso, "probe_agent_blocked", lambda w: [{"probe": "x", "ok": True}])
    monkeypatch.setattr(iso, "probe_control_still_readable",
                        lambda w: [{"probe": "c", "ok": True}])
    monkeypatch.setattr(iso, "probe_reconstruction", lambda w: [{"probe": "r", "ok": True}])
    monkeypatch.setattr(iso, "probe_sealed_blocked", lambda: [{"probe": "s", "ok": True}])
    # evaluator can no longer grade -> the "don't lock the evaluator out" direction broke
    monkeypatch.setattr(iso, "probe_evaluator_can_grade",
                        lambda w: [{"probe": "e", "ok": False}])
    monkeypatch.setattr(iso, "measure_residual_risks", lambda w: [])
    monkeypatch.setattr(iso, "_emit", lambda *a, **k: None)
    # expect_owner=False so this fails ONLY because of the evaluator probe. With the
    # default True the tmp tree fails the ownership check too, and the test would pass
    # even if the gate ignored the evaluator entirely - it would be asserting the wrong
    # thing. That is exactly the defect this test is meant to catch, so pin it down.
    assert iso.static_check(wt, expect_owner=False) == [], "tree must be clean here"
    assert iso.verify(wt, as_json=True, expect_owner=False) == 1