"""Exercise the #253 hold-out discipline on real layouts, without a model.

WHY
    holdout.py enforces three refusals: no plan without a freeze, no result from a
    candidate other than the frozen one, and no result timestamped before the
    freeze. This drives them through a full six-slot run, now on two real layouts
    instead of six copies of one workspace.

WHAT A LAYOUT IS
    The workcell geometry - the six zone coordinates the perception service
    publishes. A repair that rewrites the configuration wholesale and hardcodes
    one layout's coordinates passes on that layout and reverts the other; the gate
    catches it as LAYOUT_VALUES_CHANGED. Measured here as a positive and a
    negative case, because a hold-out that cannot fail proves nothing.

WHAT THIS IS NOT
    A model run. The repairs are applied by the reference fix, so what is being
    verified is the lock and the layout plumbing, not a hypothesis about repair
    behaviour.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
for path in (str(HERE), str(HERE.parents[1])):
    if path not in sys.path:
        sys.path.insert(0, path)

import hashlib                                            # noqa: E402

import holdout as H                                       # noqa: E402
import instances as I                                     # noqa: E402
import layouts                                            # noqa: E402

FAMILY_TO_INSTANCE = {"F1": "DEF-F1-REG", "F2": "DEF-F2-MAP"}
STATES = layouts.STATES


def candidate_sha():
    h = hashlib.sha256()
    for family in I.FAMILIES:
        h.update(I.artifact(family)["artifact_sha256"].encode())
        h.update((HERE / "instances.py").read_bytes())
        h.update((HERE / "layouts.py").read_bytes())
    return h.hexdigest()


def _write_twice(plan, sha, freeze):
    slot = plan.slot_ids[2]
    plan.record(slot, "PASS", evaluated_sha=sha, at=freeze.frozen_at + 1)
    return plan.record(slot, "PASS", evaluated_sha=sha)


def _hardcode_trap():
    """A repair that hardcodes L1's geometry must fail on L2."""
    import re
    with tempfile.TemporaryDirectory() as tmp:
        root = I.materialize("DEF-F1-REG", Path(tmp) / "c", "v2", "L2")
        cfg = root / "config" / "week1.yaml"
        text = re.sub(r"tracked_objects:.*",
                      "tracked_objects: ['target_box_a', 'target_box_b']",
                      cfg.read_text(encoding="utf-8"))
        cfg.write_text(layouts.apply_to_config(text, "L1"), encoding="utf-8")
        ok, payload = I.check("DEF-F1-REG", root, "v2")
    return ok, payload


def main():
    sha = candidate_sha()
    freeze = H.Freeze(candidate_sha=sha, source_run_id="v2-matrix",
                      selection_basis="best contract-gate candidate after the v2 run",
                      repair_runs=24)
    plan = H.HoldoutPlan(("F1", "F2"), STATES, freeze)

    problems, gates = [], {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        slot_no = 0
        for slot in plan.slot_ids:
            family, state = slot.split("|")
            layout = list(layouts.LAYOUTS)[slot_no % 2]
            slot_no += 1
            instance = FAMILY_TO_INSTANCE[family]
            root = tmp / ("%s-%s" % (family, state))
            # F2 has no configuration, so a layout is only meaningful for F1;
            # recording that rather than pretending the slot varies is the point.
            applied = layout if family == "F1" else None
            I.materialize(instance, root, "v2", applied)
            broken_ok, broken_payload = I.check(instance, root, "v2")
            I.apply_reference_fix(instance, root)
            fixed_ok, fixed_payload = I.check(instance, root, "v2")
            gates[slot] = {"layout": applied, "injected": broken_payload.get("code"),
                           "repaired": fixed_payload.get("code")}
            if broken_ok:
                problems.append("%s: the injected workspace passed the gate" % slot)
            if not fixed_ok:
                problems.append("%s: the reference repair did not pass (%s)"
                                % (slot, fixed_payload.get("code")))
            plan.record(slot, "PASS" if fixed_ok else "FAIL",
                        evaluated_sha=H.assert_frozen(freeze, sha) and sha)

    trap_ok, trap_payload = _hardcode_trap()
    if trap_ok:
        problems.append("the hardcoding trap passed; a held-out layout proved nothing")

    refusals = {}
    fresh = H.HoldoutPlan(("F1", "F2"), STATES, freeze)
    for name, thunk, expect in (
            ("no freeze", lambda: H.HoldoutPlan(("F1", "F2"), STATES, None),
             "requires a freeze"),
            ("wrong candidate", lambda: H.assert_frozen(freeze, "0" * 64),
             "is not the frozen candidate"),
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
        "gates": gates,
        "counts": report["counts"],
        "hardcode_trap": {"passed": trap_ok, "code": trap_payload.get("code")},
        "refusals": refusals,
        "problems": problems,
        "ok": ok,
    }, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
