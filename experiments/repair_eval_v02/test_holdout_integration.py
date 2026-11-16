"""The hold-out lock must work on the real instances, not only in isolation."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for path in (str(HERE), str(HERE.parents[1])):
    if path not in sys.path:
        sys.path.insert(0, path)


def test_the_six_slot_plan_runs_and_every_refusal_fires():
    """All four refusals must raise, and raise for the stated reason.

    The first run of this exercise reported ok while two refusals had never been
    exercised: the timestamp check hit "already recorded" first, and the
    second-write check was written as one-call-or-another, which short-circuits
    because the first call returns a truthy dict. Both are fixed, and the driver
    now asserts the message as well as the exception.
    """
    import dry_run_holdout as D
    assert D.main() == 0


def test_the_plan_counts_holdout_runs_separately_from_repairs():
    import dry_run_holdout as D
    import holdout as H
    sha = D.candidate_sha()
    freeze = H.Freeze(candidate_sha=sha, source_run_id="F1-B-r1",
                      selection_basis="test", repair_runs=24)
    plan = H.HoldoutPlan(("F1", "F2"), D.STATES, freeze)
    counts = plan.counts()
    assert counts["repair_runs"] == 24
    assert counts["holdout_executions"] == 0
    assert counts["reported_separately"] is True
