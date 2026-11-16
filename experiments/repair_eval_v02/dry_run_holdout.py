"""Exercise the #253 hold-out discipline end to end, without a model.

WHY
    holdout.py enforces three refusals: no plan without a freeze, no result from a
    candidate other than the frozen one, and no result timestamped before the
    freeze. Those are the rules that make "we did not peek" checkable, and until
    now they had not been driven through a whole six-slot run against the real
    instances - only unit-tested in isolation.

WHAT THIS RUNS
    A freeze over the instance artifacts, a plan of 6 slots (2 families x 3
    states), and one scripted repair per slot whose outcome comes from the sealed
    gate. Then the negative paths, each of which must raise.

WHAT IT DOES NOT DO
    It is not the retained-scenario check. The instances carry no layout or state
    variation yet, so the six slots differ only by label: three copies of F1 and
    three of F2. Giving them real variation is the same design work as fixing the
    task text, and until that exists this exercise proves the lock works, not that
    the house is furnished.
"""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
for path in (str(HERE), str(HERE.parents[1])):
    if path not in sys.path:
        sys.path.insert(0, path)

import holdout as H  # noqa: E402
import instances as I  # noqa: E402

FAMILY_TO_INSTANCE = {"F1": "DEF-F1-REG", "F2": "DEF-F2-MAP"}
STATES = ("5101", "5102", "5103")


def candidate_sha():
    """A fingerprint of what would be frozen: the instance artifacts themselves."""
    h = hashlib.sha256()
    for family in I.FAMILIES:
        info = I.artifact(family)
        h.update(info["artifact_sha256"].encode())
        h.update((HERE / "instances.py").read_bytes())
    return h.hexdigest()


def run_slot(instance, root):
    """Materialise, apply the reference repair, and ask the sealed gate."""
    I.materialize(instance, root)
    broken_ok, _ = I.check(instance, root)
    I.apply_reference_fix(instance, root)
    fixed_ok, _ = I.check(instance, root)
    return broken_ok, fixed_ok


def _write_twice(plan, sha, freeze):
    """Record one slot, then try again.

    Writing it as one-call-or-another looked fine and never ran the second
    call: the first returns a truthy dict, so the or short-circuits and the
    check reports a pass it never tested.
    """
    slot = plan.slot_ids[2]
    plan.record(slot, "PASS", evaluated_sha=sha, at=freeze.frozen_at + 1)
    return plan.record(slot, "PASS", evaluated_sha=sha)


def main():
    sha = candidate_sha()
    freeze = H.Freeze(candidate_sha=sha, source_run_id="F1-B-r1",
                      selection_basis="best contract-gate candidate from the 24-slot matrix",
                      repair_runs=24)
    plan = H.HoldoutPlan(("F1", "F2"), STATES, freeze)

    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for slot in plan.slot_ids:
            family, state = slot.split("|")
            instance = FAMILY_TO_INSTANCE[family]
            root = tmp / ("%s-%s" % (family, state))
            broken_ok, fixed_ok = run_slot(instance, root)
            if broken_ok:
                problems.append("%s: the injected workspace passed the gate" % slot)
            outcome = "PASS" if fixed_ok else "FAIL"
            plan.record(slot, outcome, evaluated_sha=H.assert_frozen(freeze, sha)
                        and sha)

    # The refusals, each on a fresh plan. Testing them on the finished plan made
    # the timestamp case fail for the wrong reason - it hit "already recorded"
    # first, so the check under test never ran and the run still looked green.
    refusals = {}
    fresh = H.HoldoutPlan(("F1", "F2"), STATES, freeze)
    for name, thunk, expect in (
            ("no freeze", lambda: H.HoldoutPlan(("F1", "F2"), STATES, None),
             "requires a freeze"),
            ("wrong candidate", lambda: H.assert_frozen(freeze, "0" * 64),
             "is not the frozen candidate"),
            # each refusal needs an untouched slot: a refused write leaves the
            # slot NOT_RUN, so reusing one lets the next check pass by accident
            ("result before the freeze",
             lambda: fresh.record(fresh.slot_ids[1], "PASS", evaluated_sha=sha,
                                  at=freeze.frozen_at - 1),
             "recorded before the candidate was frozen"),
            ("second write", lambda: _write_twice(fresh, sha, freeze),
             "already recorded"),
    ):
        try:
            thunk()
            refusals[name] = "DID NOT RAISE"
            problems.append("%s: did not raise" % name)
        except H.HoldoutError as exc:
            refusals[name] = str(exc)[:90]
            if expect not in str(exc):
                problems.append("%s: raised for the wrong reason (%s)"
                                % (name, str(exc)[:80]))

    report = plan.report()
    ok = (not problems) and report["all_terminal"] and \
        report["counts"]["holdout_executions"] == 6
    print(json.dumps({
        "candidate_sha": sha[:16],
        "slots": report["slots"],
        "counts": report["counts"],
        "reported_separately": report["counts"]["reported_separately"],
        "refusals": refusals,
        "problems": problems,
        "ok": ok,
    }, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
