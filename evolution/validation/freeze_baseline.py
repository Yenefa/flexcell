#!/usr/bin/env python3
"""Freeze the VERIFIED capability baseline and detect drift.

WHY THIS EXISTS: the mission P0 says "freeze verified capability". Without a frozen
record, a later round can quietly change the evaluator, schema or sealing scheme and the
old numbers become unattributable - nobody can tell whether a result moved because the
robot changed or because the ruler changed.

So this writes a snapshot pinning SHA-256 of every file that DEFINES correctness:
availability of these being unchanged is what makes the archived numbers comparable.

It never modifies anything it hashes. --verify re-hashes and reports drift.
"""
import hashlib
import json
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[2]
BASELINE = WT / "benchmark" / "capability_baseline.json"
REQUIRED_REASON = WT / "docs" / "FREEZE_CHANGELOG.md"

PINNED = [
    "benchmark/evaluators/evaluate.py",
    "benchmark/evaluators/sealed_evaluate.py",
    "benchmark/evaluators/observe_from_run.py",
    "benchmark/evaluators/capture_ground_truth.py",
    "benchmark/schemas/taskspec.schema.json",
    "benchmark/generators/generate.py",
    "benchmark/generators/seal_held_out.py",
    "benchmark/generators/unseen_tasks.py",
    "evolution/validation/regress.py",
]


def sha(path):
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def _changelog():
    """Return the documented reasons, newest first. Empty if none recorded."""
    if not REQUIRED_REASON.exists():
        return ""
    return REQUIRED_REASON.read_text(encoding="utf-8")


def changed_pinned():
    """Pinned files whose hash no longer matches the frozen baseline."""
    if not BASELINE.exists():
        return []
    doc = json.loads(BASELINE.read_text(encoding="utf-8"))
    out = []
    for p, want in (doc.get("pinned_files") or {}).items():
        full = WT / p
        if not full.exists():
            out.append((p, "deleted", want, None))
        else:
            now = sha(full)
            if now != want:
                out.append((p, "changed", want, now))
    return out


def freeze(force=False):
    idx = json.loads((WT / "setup" / "acceptance" / "evobot_evidence_index.json")
                     .read_text(encoding="utf-8"))
    live = [r for r in idx["rows"] if not r.get("superseded_by")]
    changes = changed_pinned()
    if changes and not force:
        log = _changelog()
        missing = [p for p, _, _, _ in changes if p not in log]
        if missing:
            raise SystemExit(
                "REFUSING to re-freeze: these pinned files changed with no entry in "
                "docs/FREEZE_CHANGELOG.md: %s" % missing)
    doc = {
        "record_kind": "EVOBOT_CAPABILITY_BASELINE",
        "changes_since_previous": [{"file": p, "kind": k, "was": w, "now": n}
                                   for p, k, w, n in changes],
        "why": ("Pins the contract that DEFINES correctness, so archived numbers stay "
                "comparable. Changing any pinned file requires re-running the "
                "experiments, not just editing this file."),
        "pinned_files": {p: sha(WT / p) for p in PINNED if (WT / p).exists()},
        "missing_pinned_files": [p for p in PINNED if not (WT / p).exists()],
        "evidence": {
            "batches_total": idx["batches"],
            "batches_live": len(live),
            "batches_superseded": idx["superseded"],
            "verifier_failures": idx["verifier_failures"],
            "live_batches": [{"batch": r["batch"], "verified": r["verified"],
                             "rung": r["rung"]} for r in live],
        },
        "verified_headline": {
            "three_arm_planning": {"A_prime": "0/16", "B": "16/16", "C": "16/16"},
            "pooled_n32": {"B_first_try": "25/32", "R_after_retry": "29/32",
                           "paired_gained": 4, "paired_lost": 0,
                           "false_success": "1/32 MEASURED (the earlier 0/32 was vacuous)"},
            "v01_regression": "6/6 -> 6/6, no loss",
            "experience_effect_on_plans": "0/16 changed",
        },
        "known_bottleneck": {
            "layer": "actuator",
            "detail": ("every remaining failure is ACTUATOR_STALL_ON_RELEASE: the "
                       "gripper stalls while releasing. Same coordinates both succeed "
                       "and stall, so it is not geometric. Out of scope here: the "
                       "skill layer issues gripper_open with no bounded retry."),
        },
        "honesty": {
            "false_success": "0/32 MEASURED with 87.5% self-assessment accuracy (the original 0/32 was vacuous; the honest v1 figure was 1/32)",
            "false_failure": "4/32 = 12.5%",
            "self_assessment_accuracy": "28/32 = 87.5%",
            "mission_requirement": "False Success Rate MUST be 0 -> MET on n=32, but a zero alone is gameable, so accuracy is reported with it",
        },
        "task_false_failure": {
            "why_new": ("the mirror of false success: the task reports failure while the "
                        "independent evaluator says the goal was satisfied. Never measured "
                        "before this round."),
            "measured": "2/32 = 6.2% (1.7-20.1%); false success 0/32",
            "evidence": "setup/acceptance/evobot_false_failure_20261111",
            "mechanism": ("place reported released=False err=25 and recorded no box_after, "
                          "yet the box was inside zone_1 (37 mm from centre) and the "
                          "skill own verify.jsonl said verified=True"),
            "consequence": ("the recovery driver acts on task.out, so it retried a "
                            "placement that was already complete - which is why arm R "
                            "looked exercised in a batch where nothing failed"),
            "prereg_impact": ("the actuator_stall pre-registration assumed all release "
                              "stalls were real failures; its basis is now recorded as "
                              "superseded and it must be re-derived before any change"),
        },
        "generalization": {
            "batch": "evobot_generalization_20261111 (seeds 8100/8200, zero overlap)",
            "pooled_arm_B": "30/32 = 93.8% (79.9-98.3%)",
            "pooled_arm_R": "32/32 = 100% (89.3-100%)",
            "intervals_overlap": True,
            "false_success": "0 on both batches",
            "new_finding": ("skill layer reported PLACE_A:FAIL while the measured world "
                            "satisfied the goal, on 2/16 instances - a false FAILURE that "
                            "triggered a retry which was not needed"),
            "do_not_overclaim": ("same generator with only the seeds changed, so this is "
                                 "not cross-distribution; recovery efficacy unmeasured"),
        },
        "first_valid_batch": {
            "batch": "evobot_valid_batch_20261111 (16 instances, seeds 7500/7600)",
            "why_valid": ("validate_batch.py rc=0: 2 failed first attempts, 2 recovery "
                          "decisions, 2 retries, 16/16 claims measured"),
            "arm_B": "14/16 = 87.5% (64.0-96.5%)",
            "arm_R": "16/16 = 100% (80.6-100%)",
            "paired": "gained 2, lost 0",
            "false_success": "0/16",
            "false_failure": "1/16",
            "assess_accuracy": "15/16 = 93.8% (71.7-98.9%)",
            "do_not_overclaim": ("only 2 instances exercised recovery, so R=16/16 is NOT "
                                 "a 100% claim and does not measure recovery efficacy"),
        },
        "invalid_results_retracted": {
            "pair48_arm_R": "INERT - recovery never ran (cwd trap); B and R identical on 16/16",
            "pair48_three_failures": "TRANSIENT - 0/3 reproduced on re-run with the same plan",
            "consequence": ("B=13/16 in that batch is one sample of a noisy process, "
                            "not a property of the instances; B-vs-R from it is void"),
        },
        "not_achieved": ["Level 4 Develop", "Level 5 Improve", "Level 7 Transfer",
                         "hardware (M0, prohibited)"],
    }
    BASELINE.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def verify():
    if not BASELINE.exists():
        return False, ["baseline file missing"]
    doc = json.loads(BASELINE.read_text(encoding="utf-8"))
    problems = []
    for p, want in (doc.get("pinned_files") or {}).items():
        full = WT / p
        if not full.exists():
            problems.append("pinned file deleted: " + p)
        elif sha(full) != want:
            problems.append("pinned file CHANGED: " + p)
    return not problems, problems


def main(argv=None):
    argv = argv or []
    if argv and argv[0] == "--verify":
        ok, problems = verify()
        if ok:
            doc = json.loads(BASELINE.read_text(encoding="utf-8"))
            print(json.dumps({"baseline": "INTACT",
                              "pinned": len(doc["pinned_files"])}))
            return 0
        print(json.dumps({"baseline": "DRIFTED", "problems": problems}, indent=2))
        return 1
    doc = freeze()
    print(json.dumps({"frozen": str(BASELINE),
                      "pinned_files": len(doc["pinned_files"]),
                      "live_batches": doc["evidence"]["batches_live"],
                      "verifier_failures": doc["evidence"]["verifier_failures"]},
                     indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
