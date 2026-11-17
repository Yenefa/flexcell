"""Freeze archived model/reference artifacts, then evaluate without a repairer.

All inputs are pinned before execution. The reference is supplied explicitly;
an injected-state observation made during evaluation is never the reference.
This runner evaluates source/config behaviour, not a Gazebo/physical outcome.
"""
import argparse
import difflib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (str(HERE), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

import evidence_archive as ARCH
import environment_receipt
import frozen_regressions as REG
import health
import holdout as H
import instances as I
import layouts


def evaluator_files():
    files = [HERE / name for name in ("evaluate_holdout.py", "holdout.py", "health.py",
             "instances.py", "layouts.py", "frozen_regressions.py", "evidence_archive.py",
             "environment_receipt.py")]
    files += list((ROOT / "benchmark" / "repair_eval" / "contracts").rglob("*.py"))
    files += [REG.CASES / name for name in REG.CASE_FILES]
    files += [HERE / "provenance_247.json"]
    return {p.relative_to(ROOT).as_posix(): health.file_sha(p) for p in files}


def create_freeze(candidate_archive, reference_archive, path, *, selection_basis,
                  reference_basis, repair_runs=0, mechanical=False):
    candidate_archive = Path(candidate_archive).resolve()
    reference_archive = Path(reference_archive).resolve()
    c, r = ARCH.verify(candidate_archive), ARCH.verify(reference_archive)
    if not c.get("candidate_sha") or not r.get("candidate_sha"):
        raise H.HoldoutError("both archives require a verified final workspace")
    instance = c["record"].get("instance")
    if instance not in I.FAMILIES or r["record"].get("instance") != instance:
        raise H.HoldoutError("candidate and reference must name the same registered instance")
    if not mechanical and c["record"].get("qualification") != "REAL_MODEL_RUN|INSTANCE":
        raise H.HoldoutError("formal holdout requires an archived model candidate")
    if not r["record"].get("source_sha") or not r["record"].get("selection_basis"):
        raise H.HoldoutError("reference requires predeclared source and selection basis")
    freeze = H.Freeze(c["candidate_sha"], c["record"]["slot_id"], selection_basis,
                      repair_runs=repair_runs, reference_sha=r["candidate_sha"],
                      reference_basis=reference_basis)
    payload = {"schema": "evobot.comparative_freeze/1", "freeze": freeze.as_dict(),
               "freeze_sha": freeze.sha(), "instance": instance,
               "task_variant": c["record"].get("task_variant", "v2"),
               "candidate_archive": str(candidate_archive),
               "reference_archive": str(reference_archive),
               "candidate_archive_sha": health.file_sha(candidate_archive / "archive.json"),
               "reference_archive_sha": health.file_sha(reference_archive / "archive.json"),
               "candidate_source_sha": c["record"].get("source_sha"),
               "reference_source_sha": r["record"].get("source_sha"),
               "candidate_qualification": c["record"].get("qualification"),
               "artifact_hash_algorithm": "sha256-file-inventory",
               "environment": environment_receipt.capture(),
               "evaluator_files": evaluator_files(), "mechanical_only": mechanical}
    # Exclusive creation makes a new version a new freeze, not a replacement.
    with Path(path).open("x", encoding="utf-8") as out:
        json.dump(payload, out, indent=2, ensure_ascii=False)
    return payload


def transfer_edit(before, after, target):
    """Replay only the recorded changes; do not regenerate or repair anything.

    Geometry unchanged by the model stays owned by the held-out environment.
    A changed hunk whose original bytes no longer match fails closed, including
    repairs that hardcode a layout. Both original/final full files remain bound
    by the archive SHA, and the diff digest is emitted in the slot report.
    """
    old, new = before.splitlines(keepends=True), after.splitlines(keepends=True)
    text = target
    operations = difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes()
    for tag, a, b, c, d in reversed(operations):
        if tag == "equal":
            continue
        needle, replacement = "".join(old[a:b]), "".join(new[c:d])
        if not needle:
            # Anchor insertions in an unchanged neighbouring line. An ambiguous
            # anchor is not permission to guess which occurrence to edit.
            if a < len(old):
                needle = old[a]
                replacement += needle
            elif old:
                needle = old[-1]
                replacement = needle + replacement
            else:
                if text:
                    raise ValueError("nonempty target for empty-file insertion")
                text = replacement
                continue
        if text.count(needle) != 1:
            raise ValueError("frozen edit does not apply uniquely to held-out input")
        text = text.replace(needle, replacement, 1)
    return text


def layout_integrity(instance, root, layout):
    if instance != "DEF-F1-REG":
        return {"status": "NOT_APPLICABLE", "reason": "F2 source gate does not execute geometry"}
    import yaml
    params = yaml.safe_load((root / "config/week1.yaml").read_text())["observe_server"]["ros__parameters"]
    expected = dict(zip(layouts.CONFIG_KEYS, layouts.layout_values(layout).values()))
    changed = [key for key, value in expected.items() if key not in params
               or not math.isfinite(float(params[key])) or abs(float(params[key]) - value) > 1e-9]
    return {"status": "FAIL" if changed else "PASS", "changed_or_missing": changed}


def evaluate(freeze_path, outdir):
    freeze_path, outdir = Path(freeze_path), Path(outdir)
    raw = json.loads(freeze_path.read_text(encoding="utf-8"))
    freeze = H.Freeze(**raw["freeze"])
    if freeze.sha() != raw["freeze_sha"]:
        raise H.HoldoutError("freeze record changed")
    for rel, sha in raw["evaluator_files"].items():
        if health.file_sha(ROOT / rel) != sha:
            raise H.HoldoutError("evaluator/corpus changed since freeze: %s" % rel)
    archives = {}
    for arm in ("candidate", "reference"):
        root = Path(raw[arm + "_archive"])
        if health.file_sha(root / "archive.json") != raw[arm + "_archive_sha"]:
            raise H.HoldoutError("archive manifest changed since freeze")
        manifest = ARCH.verify(root)
        expected = freeze.candidate_sha if arm == "candidate" else freeze.reference_sha
        if manifest["candidate_sha"] != expected:
            raise H.HoldoutError("%s is not the frozen artifact" % arm)
        archives[arm] = root
    if not freeze.reference_sha:
        raise H.HoldoutError("reference must be fixed before any execution")
    outdir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(freeze_path, outdir / "freeze.json")
    plan = H.HoldoutPlan(tuple(layouts.LAYOUTS), layouts.STATES, freeze)
    details = {}
    execution_environment = environment_receipt.capture()

    def persist():
        report = plan.report()
        report.update(mechanical_only=raw["mechanical_only"], execution_backend="sealed_source_gate",
                      admission_status="NOT_VERIFIED_PHYSICALLY",
                      candidate_source_sha=raw["candidate_source_sha"],
                      reference_source_sha=raw["reference_source_sha"],
                      candidate_qualification=raw["candidate_qualification"],
                      gate_independent="NOT_RUN", ordinary_task_regression="NOT_RUN",
                      physical_regression_coordination="PENDING_247_CONFIRMATION",
                      state_coverage="state labels only; no physical initial-state execution",
                      provenance=json.loads((HERE / "provenance_247.json").read_text(encoding="utf-8")),
                      environment=execution_environment,
                      frozen_environment=raw["environment"],
                      details=details, concluded_at=time.time())
        ARCH.write_json(outdir / "report.json", report)
        return report

    persist()
    for arm, archive in archives.items():
        expected = freeze.candidate_sha if arm == "candidate" else freeze.reference_sha
        plan.record_regressions(arm, REG.run(archive / "candidate", expected))
        persist()
    instance = raw["instance"]
    rel = I.editable_rel(instance)
    for slot in plan.slot_ids:
        layout, state = slot.split("|")
        details[slot] = {}
        for arm, archive in archives.items():
            expected = freeze.candidate_sha if arm == "candidate" else freeze.reference_sha
            root = outdir / "slots" / slot.replace("|", "-") / arm
            detail = {"evaluated_sha": expected, "layout": layout, "initial_state": state,
                      "evidence_path": str(root)}
            outcome = "FAIL"
            try:
                ARCH.verify(archive)
                I.materialize(instance, root, raw["task_variant"], layout)
                original = (archive / "initial_candidate" / rel).read_text(encoding="utf-8")
                final = (archive / "candidate" / rel).read_text(encoding="utf-8")
                diff = list(difflib.unified_diff(original.splitlines(True), final.splitlines(True)))
                detail["edit_sha256"] = H.digest(diff)
                target = root / rel
                target.write_text(transfer_edit(original, final, target.read_text(encoding="utf-8")),
                                  encoding="utf-8")
                ok, payload = I.check(instance, root, raw["task_variant"])
                health.gate_terminal(ok, payload)
                detail["gate"] = payload
                detail["layout_integrity"] = layout_integrity(instance, root, layout)
                # Candidate legality: immutable task, hidden evaluator and all
                # files outside the exact editable file must survive unchanged.
                before_inv = health.inventory(archive / "initial_candidate")
                after_inv = health.inventory(archive / "candidate")
                illegal = [p for p in set(before_inv) | set(after_inv)
                           if p != rel and before_inv.get(p) != after_inv.get(p)]
                detail["illegal_changes"] = sorted(illegal)
                ARCH.verify(archive)
                outcome = ("PASS" if ok and not illegal
                           and detail["layout_integrity"]["status"] != "FAIL" else "FAIL")
            except Exception as exc:
                detail["error"] = "%s: %s" % (type(exc).__name__, exc)
            detail["status"] = outcome
            details[slot][arm] = detail
            plan.record(slot, outcome, evaluated_sha=expected, arm=arm)
            persist()
    return persist()


def export_reference(instance, source_sha, destination, basis):
    """Export a named Git baseline, not the evaluation's injected observation."""
    commit = health.checked_run(["git", "rev-parse", source_sha + "^{commit}"], cwd=ROOT)
    if commit.returncode != 0:
        raise ValueError("reference commit unavailable")
    full_sha = commit.stdout.strip()
    rel = I.CONFIG_REL if instance == "DEF-F1-REG" else I.FSM_REL
    version = health.checked_run(["git", "show", full_sha + ":" + rel], cwd=ROOT)
    if version.returncode != 0:
        raise ValueError("reference source file unavailable")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        I.materialize(instance, root / "candidate", "v2")
        shutil.copytree(root / "candidate", root / "initial_candidate")
        (root / "candidate" / I.editable_rel(instance)).write_text(version.stdout, encoding="utf-8")
        return ARCH.preserve(root, Path(destination), {
            "slot_id": "BASELINE-" + full_sha, "source_sha": full_sha,
            "instance": instance, "task_variant": "v2", "qualification": "BASELINE_COMMIT",
            "selection_basis": basis})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    ref = sub.add_parser("reference")
    ref.add_argument("--instance", choices=I.FAMILIES, required=True)
    ref.add_argument("--source-sha", required=True)
    ref.add_argument("--basis", required=True)
    ref.add_argument("--out", required=True)
    freeze = sub.add_parser("freeze")
    freeze.add_argument("--candidate-archive", required=True)
    freeze.add_argument("--reference-archive", required=True)
    freeze.add_argument("--selection-basis", required=True)
    freeze.add_argument("--reference-basis", required=True)
    freeze.add_argument("--repair-runs", type=int, required=True)
    freeze.add_argument("--out", required=True)
    run = sub.add_parser("evaluate")
    run.add_argument("--freeze", required=True)
    run.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    if args.command == "reference":
        export_reference(args.instance, args.source_sha, args.out, args.basis)
    elif args.command == "freeze":
        create_freeze(args.candidate_archive, args.reference_archive, args.out,
                      selection_basis=args.selection_basis, reference_basis=args.reference_basis,
                      repair_runs=args.repair_runs)
    else:
        report = evaluate(args.freeze, args.out)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["checks_passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
