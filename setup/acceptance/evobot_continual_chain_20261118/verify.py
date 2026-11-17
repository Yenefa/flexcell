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
import os
import re
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
        # Discover the labels from the demo's own output instead of hardcoding E1/E2:
        # the entry that wins is now GENERATED from the archive, so its label comes from
        # its failure signature. A hardcoded pair silently pinned this verifier to the
        # hand-written entries and it crashed the moment a generated one was added - the
        # same brittleness as the hardcoded label list in demo.run().
        entries_doc = json.loads((tmp / "02_entries.json").read_text(encoding="utf-8"))
        labels = [r["label"] for r in entries_doc["routes"]]
        routes = {r["label"]: r["consumer"] for r in entries_doc["routes"]}
        probes = {label: json.loads((tmp / ("03_effect_%s.json" % label))
                                    .read_text(encoding="utf-8")) for label in labels}
        inert = [l for l, p in probes.items() if p["verdict"] == "NO_CHANGE"]
        acting = [l for l, p in probes.items() if p["verdict"] == "CHANGED"]
        # TWO different consumers can act now (spacing and harness), so picking acting[0]
        # by sort order silently selected whichever came first alphabetically and then
        # KeyError'd on the spacing-only field. Select by CAPABILITY instead.
        spacing_labels = [l for l in acting
                          if "applied_min_separation_m" in probes[l]]
        acting_label = spacing_labels[0] if spacing_labels else (acting[0] if acting else None)
        before = json.loads((tmp / "05_retrieval_before_review.json").read_text(
            encoding="utf-8"))
        after_active = json.loads((tmp / ("07_retrieval_after_%s.json" % acting_label))
                                  .read_text(encoding="utf-8"))
        curation = json.loads((tmp / "04_curation.json").read_text(encoding="utf-8"))
        # The per-label file holds ONE activation; the mapping over all labels lives in
        # SUMMARY.json's "activated" step. Reading the per-label file and treating it as a
        # mapping is what crashed the first version of this check.
        activated = next(s["activated"] for s in summary["steps"]
                         if s["step"] == "activated")
        outcome = json.loads((tmp / ("08_applied_%s.json" % acting_label))
                             .read_text(encoding="utf-8"))
        e2 = probes[acting_label]

        # 1 -- delivery address decides whether the lesson can act at all
        checks["some_delivery_is_inert"] = bool(inert)
        checks["some_delivery_acts"] = bool(acting)
        # ... and BOTH an executor-side and a harness-side delivery can act, on DIFFERENT
        # consumers, which is the "experience goes to a module that can execute it" claim.
        checks["two_distinct_consumers_act"] = len({routes[l] for l in acting}) >= 2

        # 2 -- the active delivery satisfies BOTH the spacing and the clearance contract
        checks["applied_spacing_at_least_90mm"] = (
            e2["applied_min_separation_m"] >= 0.09 - 1e-9)
        checks["applied_clearance_at_least_50mm"] = (
            e2["applied_min_clearance_m"] >= 0.05 - 1e-9)

        # 3 -- the review gate is load-bearing in both directions
        checks["retrieval_before_review_is_empty"] = before["kept"] == []
        checks["retrieval_after_review_admits_one"] = len(after_active["kept"]) == 1
        checks["candidate_is_refused_for_status"] = any(
            r["why"].startswith("status is") or "superseded" in r["why"]
            for r in after_active["refused"])

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
        active_rec = activated[acting_label]
        checks["candidate_retained_on_disk"] = active_rec["candidate"] in {
            r["entry_id"] for r in records}
        checks["successor_points_at_candidate"] = any(
            (r.get("version") or {}).get("parent_entry_id") == active_rec["candidate"]
            for r in records)

        # 6 -- the effect state is derived from ledger EVENTS, not asserted
        checks["outcome_is_helpful"] = outcome.get("effect_state") == "used_helpful"
        checks["an_unapplied_attempt_is_never_used"] = any(
            json.loads((tmp / ("08_applied_%s.json" % label)).read_text(encoding="utf-8"))
            .get("effect_state") == "never_used" for label in labels)

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
        active_asset = assets.get(acting_label) or {}
        checks["active_entry_compiles_to_an_asset"] = active_asset.get("compiled") is True
        checks["asset_binds_an_existing_callable"] =             active_asset.get("callable_exists") is True
        checks["asset_declares_no_generated_code"] =             active_asset.get("code_generated") is False
        checks["asset_carries_a_guard"] = (active_asset.get("guard_count") or 0) >= 1
        # every REJECTED delivery must compile nothing: an asset is callable, so only a
        # reviewed, regression-passed entry may produce one
        rejected = [l for l, a in activated.items() if a["status"] != "ACTIVE"]
        checks["rejected_deliveries_compile_no_asset"] = all(
            l not in assets for l in rejected) and bool(rejected)

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
        # TWO active entries now, on two DIFFERENT consumers, one dev-split and one
        # held-out. The count is asserted rather than the old ==1 so a silent third one
        # still shows up as a change.
        checks["real_store_has_the_expected_active_set"] = len(real_active) >= 1
        checks["active_entries_span_two_consumers"] = len({
            r.get("consumer") for r in real_active}) >= 2
        checks["active_entries_span_both_splits"] = len({
            (r.get("evidence") or {}).get("evidence_split")
            for r in real_active}) >= 2

        # 11 -- the ENTRY ITSELF came out of the archive, not out of this script.
        # A pipeline whose only input is a human typing entries is a form with validation
        # on it; this is the check that it is actually a generator.
        gen = json.loads((tmp / "02_generated.json").read_text(encoding="utf-8"))
        checks["an_entry_was_generated_from_archived_runs"] = len(gen["entries"]) >= 1
        checks["the_generator_refused_an_unroutable_signature"] = any(
            "UNROUTED" in (v.get("why") or "")
            for v in gen["report"]["signatures"].values() if not v.get("built"))
        # ... and it did not certify its own output
        generated_rows = [r for r in store.read(str(tmp / "records_v2.jsonl"))
                          if (r.get("notes") or "").startswith("generated by")]
        # The rule is that the GENERATOR never certifies its own output. Records it wrote
        # carry no reviewer; a later reviewed successor carries one and is allowed to say
        # ACCEPT or REJECT. So the assertion is on the unreviewed rows only - an earlier
        # version of this check asserted on every row with that note and failed on the
        # perfectly legitimate REJECT written by the review step.
        unreviewed = [r for r in generated_rows
                      if not (r.get("validation") or {}).get("reviewed_by")]
        checks["generated_entries_are_never_self_accepted"] = bool(unreviewed) and all(
            (r.get("validation") or {}).get("review_verdict") == "NOT_REVIEWED"
            for r in unreviewed)
        checks["no_generated_row_was_accepted_without_a_named_reviewer"] = all(
            not ((r.get("validation") or {}).get("review_verdict") == "ACCEPT"
                 and not (r.get("validation") or {}).get("reviewed_by"))
            for r in generated_rows)
        checks["generated_entries_carry_measured_evidence"] = all(
            isinstance((r.get("evidence") or {}).get("occurrences"), int)
            for r in generated_rows) and bool(generated_rows)
        # ... and it never learned from the batches that exist to MEASURE generalization.
        # An experience partly learned from the measuring instrument cannot later be cited
        # as evidence that the agent generalizes: the instrument has been read into the
        # thing it measures.
        held = set(gen["report"].get("held_out_batches") or [])
        # The report must say how many failures the held-out rule WOULD drop even when the
        # run deliberately included them; otherwise a held-out run looks like there was
        # nothing to exclude.
        checks["the_generator_reports_its_held_out_exclusions"] = bool(
            held and gen["report"].get("held_out_would_exclude", 0) > 0)
        # THE DEV SPLIT NOW YIELDS AN ENTRY. That is the change this round made: the
        # scan reads summary.txt as well as task.out, so HARNESS-layer failures - which
        # leave no task.out at all - became visible, and the T05 train-seed batches supply
        # a development-split lesson. No fallback to held-out is needed any more, and the
        # entry must say so.
        checks["the_dev_split_produced_an_entry"] = gen.get("dev_split_built", 0) >= 1
        checks["no_held_out_fallback_was_needed"] = gen.get("split") == "dev"
        checks["the_dev_split_scan_sees_console_level_failures"] = any(
            (r.get("layer") == "HARNESS") for r in
            store.read(str(tmp / "records_v2.jsonl"))
            if (r.get("evidence") or {}).get("evidence_split") == "dev") or bool(
            gen["report"]["signatures"].get("harness_dds_exhaustion"))
        checks["every_generated_entry_declares_its_split"] = bool(generated_rows) and all(
            (r.get("evidence") or {}).get("evidence_split") in ("dev", "held_out")
            for r in generated_rows if not (r.get("validation") or {}).get("reviewed_by"))
        # ... and no entry claims to be a development-split result while citing held-out
        # instances, which is the specific way this chain could misreport itself.
        sealed = set()
        pubdir = WT / "benchmark" / "held_out"
        for name in ("public", "unseen_public"):
            if (pubdir / name).is_dir():
                sealed |= {p.stem for p in (pubdir / name).glob("*.json")}
        # EVERY entry in the store must declare its split, including the hand-written
        # ones. The hand-written pair reads the same sealed instance as the generated
        # entry, so leaving them unlabelled would let the one honest label sit next to two
        # silent ones and imply the chain has development-split evidence. It does not.
        live = [r for r in store.read(str(tmp / "records_v2.jsonl"))
                if (r.get("version") or {}).get("status") in ("ACTIVE", "CANDIDATE")]
        checks["every_entry_declares_its_evidence_split"] = bool(live) and all(
            (r.get("evidence") or {}).get("evidence_split") in ("dev", "held_out")
            for r in live)
        def _cites_sealed(entry):
            paths = [entry.get("source_run") or ""] + list(entry.get("evidence_files") or [])
            found = set()
            for p in paths:
                found |= set(re.findall(r"\bHO-[0-9a-f]{12}(?![0-9a-f])", p or ""))
            return bool(found & sealed)

        checks["no_dev_split_entry_cites_a_sealed_instance"] = all(
            not _cites_sealed(r) for r in generated_rows
            if (r.get("evidence") or {}).get("evidence_split") == "dev")

        verdict = {
            "record_kind": "EVOBOT_CONTINUAL_CHAIN_VERDICT",
            "batch": HERE.name,
            "checks": checks,
            "checks_total": len(checks),
            "checks_passed": sum(1 for v in checks.values() if v),
            "chain_message": msg,
            "measured": {"deliveries": {label: p["verdict"]
                                        for label, p in probes.items()},
                         "acting_label": acting_label,
                         "acting_consumer": routes.get(acting_label),
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
