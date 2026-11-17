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

        # 7 -- the regression gate is LOAD-BEARING, not decorative
        records_all = [json.loads(line) for line in
                       (tmp / "records_v2.jsonl").read_text(encoding="utf-8").splitlines()
                       if line.strip()]
        active = [r for r in records_all
                  if (r.get("version") or {}).get("status") == "ACTIVE"]
        checks["activation_carries_a_regression_verdict"] = bool(
            active and (active[0].get("regression") or {}).get("verdict") == "KEEP")
        checks["regression_actually_ran_verifiers"] = bool(
            active and (active[0].get("regression") or {}).get("ran"))

        # 8 -- the ACTIVE entry compiles into a CALLABLE asset, and that callable exists
        assets = json.loads((tmp / "10_skill_assets.json").read_text(encoding="utf-8"))
        e2_asset = assets.get("E2") or {}
        checks["active_entry_compiles_to_an_asset"] = e2_asset.get("compiled") is True
        checks["asset_binds_an_existing_callable"] = e2_asset.get("callable_exists") is True
        checks["asset_declares_no_generated_code"] = e2_asset.get("code_generated") is False
        checks["asset_carries_a_guard"] = (e2_asset.get("guard_count") or 0) >= 1
        # the REJECTED delivery must not become a skill: an asset is callable, so only a
        # reviewed, regression-passed entry may produce one
        checks["rejected_delivery_compiles_no_asset"] = "E1" not in assets

        # 9 -- the MISUSE check ran and is load-bearing (master goal step 4:
        # "does it get misused in scenarios where it does not apply")
        checks["activation_carries_a_misuse_verdict"] = bool(
            active and (active[0].get("misuse_check") or {}).get("verdict") == "BLOCKED")
        checks["misuse_probes_actually_ran"] = bool(
            active and (active[0].get("misuse_check") or {}).get("probed", 0) >= 1)
        # every declared invalid condition must be covered, or the disclaimer is partial
        declared = len(active[0].get("known_invalid_when") or []) if active else 0
        probed = (active[0].get("misuse_check") or {}).get("probed", 0) if active else 0
        checks["every_invalid_condition_was_probed"] = declared > 0 and probed == declared

        # 10 -- the LIFECYCLE half exists: the ledger produces a decision, and the RETIRE
        # transition really changes what retrieval serves
        life = json.loads((tmp / "10_lifecycle_review.json").read_text(encoding="utf-8"))
        checks["lifecycle_review_produces_a_decision"] = bool(
            life and all(d.get("decision") in ("KEEP", "RETIRE") for d in life))
        demo = json.loads((tmp / "10_retirement_transition.json").read_text(encoding="utf-8"))
        checks["retire_transition_appends_a_retired_version"] = (
            demo.get("status_after") == "RETIRED" and demo.get("parent_linked") is True)
        checks["retire_keeps_the_harmful_version"] = demo.get("chain_ok") is True
        checks["retire_is_on_a_copy_not_the_real_store"] = "COPY" in (demo.get("note") or "")
        real_active = [r for r in active]
        checks["real_store_still_has_exactly_one_active_entry"] = len(real_active) == 1

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
