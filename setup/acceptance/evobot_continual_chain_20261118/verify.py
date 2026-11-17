#!/usr/bin/env python3
"""Verify the continual chain: entry -> consumer -> behaviour -> verification.

WHY A VERIFIER AND NOT A REPORT
    Every directory under setup/acceptance that starts with "evobot" is required by
    benchmark/tests/test_evidence_discipline.py to contain a machine check. The rule
    exists because eighteen rounds published batches with a README and no verifier, and
    a claim nobody can re-run is a narrative. This batch is no exception, so the claims
    it makes are re-derived here from the code and the archived runs - not read back out
    of the SUMMARY it ships with.

WHAT IT ASSERTS (each one is a claim that could be false)
    1. the same lesson, offered to two consumers, is inert at one and active at the other
    2. the active delivery widens spacing AND keeps the clearance contract
    3. retrieval refuses everything before an independent review and admits exactly one
       entry after it
    4. curation refuses a duplicate and a conflict instead of filing them
    5. activation APPENDS a successor: the candidate stays on disk and the chain verifies
    6. the ledger's verdict for the used entry is "used_helpful", computed from events
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
sys.path.insert(0, str(WT / "evolution" / "experience"))


def _load(name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        name, WT / "evolution" / "experience" / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    demo = _load("demo_continual")
    tmp = Path(tempfile.mkdtemp(prefix="continual_"))
    checks = {}

    try:
        summary = demo.run(str(tmp))
        e1 = json.loads((tmp / "03_effect_E1.json").read_text(encoding="utf-8"))
        e2 = json.loads((tmp / "03_effect_E2.json").read_text(encoding="utf-8"))
        before = json.loads((tmp / "05_retrieval_before_review.json").read_text(
            encoding="utf-8"))
        after_e2 = json.loads((tmp / "07_retrieval_after_E2.json").read_text(
            encoding="utf-8"))
        curation = json.loads((tmp / "04_curation.json").read_text(encoding="utf-8"))
        activated = json.loads((tmp / "06_activated_E2.json").read_text(encoding="utf-8"))
        outcome = json.loads((tmp / "08_applied_E2.json").read_text(encoding="utf-8"))

        # 1 -- delivery address decides whether the lesson can act at all
        checks["planner_side_is_inert"] = e1["verdict"] == "NO_CHANGE"
        checks["executor_side_acts"] = e2["verdict"] == "CHANGED"

        # 2 -- the active delivery satisfies BOTH the spacing and the clearance contract
        checks["applied_spacing_at_least_90mm"] = e2["applied_min_separation_m"] >= 0.09 - 1e-9
        checks["applied_clearance_at_least_50mm"] =             e2["applied_min_clearance_m"] >= 0.05 - 1e-9

        # 3 -- the review gate is load-bearing in both directions
        checks["retrieval_before_review_is_empty"] = before["kept"] == []
        checks["retrieval_after_review_admits_one"] = len(after_e2["kept"]) == 1
        checks["candidate_is_refused_for_status"] = any(
            r["why"].startswith("status is") for r in after_e2["refused"])

        # 4 -- curation refuses redundancy and contradiction
        checks["duplicate_refused"] = curation["duplicate_attempt"]["decision"] == "DUPLICATE"
        checks["conflict_refused"] = curation["conflict_attempt"]["decision"] == "CONFLICT"

        # 5 -- activation is append-only and the chain still verifies
        records = [json.loads(line) for line in
                   (tmp / "records_v2.jsonl").read_text(encoding="utf-8").splitlines()
                   if line.strip()]
        store = _load("store")
        ok, msg = store.verify_chain(str(tmp / "records_v2.jsonl"))
        checks["chain_verifies"] = ok
        checks["candidate_retained_on_disk"] = activated["candidate"] in {
            r["entry_id"] for r in records}
        checks["successor_points_at_candidate"] = any(
            (r.get("version") or {}).get("parent_entry_id") == activated["candidate"]
            for r in records)

        # 6 -- the effect state is derived from ledger EVENTS, not asserted
        checks["outcome_is_helpful"] = outcome.get("effect_state") == "used_helpful"
        checks["skipped_attempt_is_never_used"] = (
            json.loads((tmp / "08_applied_E1.json").read_text(encoding="utf-8"))
            .get("effect_state") == "never_used")

        verdict = {
            "record_kind": "EVOBOT_CONTINUAL_CHAIN_VERDICT",
            "batch": HERE.name,
            "checks": checks,
            "checks_total": len(checks),
            "checks_passed": sum(1 for v in checks.values() if v),
            "chain_message": msg,
            "measured": {"E1_planner_side": e1["verdict"],
                         "E2_executor_side": e2["verdict"],
                         "spread_separation_m": e2.get("applied_min_separation_m"),
                         "clearance_m": e2.get("applied_min_clearance_m")},
            "honest_limits": summary.get("honest_limits"),
            "level": ("Implemented + Unit Tested + offline chain measurement; "
                      "NOT Simulation Tested (no new robot run this round)"),
        }
        (HERE / "verify_result.json").write_text(
            json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(verdict, indent=2))
        return 0 if all(checks.values()) else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
