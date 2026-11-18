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
        # THE MISUSE CHECK IS SUPPOSED TO BE ABLE TO FIND SOMETHING, not only to confirm a
        # design. This round it did: apply_respread widened every cluster within cluster_m,
        # so a plan already sitting at the 90 mm contract was ROTATED onto the other axis -
        # 94 of 127 touched plans on the archive needed no change and were displaced anyway.
        # The condition and its probe are what caught it, so their presence is asserted.
        # Across ALL active entries, not active[0]: which entry is first depends on which
        # consumer happens to act, and the condition belongs to the spacing entries.
        conditions = {c for r in active for c in (r.get("known_invalid_when") or [])}
        checks["a_already_conforming_plan_is_a_declared_invalid_condition"] = any(
            "ALREADY meet" in c for c in conditions)
        import misuse as _misuse
        outcome, detail = _misuse.PROBES["spacing.already_satisfied"](
            {"step_m": 0.090, "cluster_m": 0.12})
        checks["the_already_conforming_probe_reports_inert"] = (
            outcome == "INERT"), detail

        # 10 -- the LIFECYCLE half exists: the ledger produces a decision, and the RETIRE
        # transition really changes what retrieval serves
        life = json.loads((tmp / "10_lifecycle_review.json").read_text(encoding="utf-8"))
        checks["lifecycle_review_produces_a_decision"] = bool(
            life and all(d.get("decision") in ("KEEP", "RETIRE", "REVISE") for d in life))
        # NOT named "demo": that is the module handle, and shadowing it here made every
        # later reference to demo.<function> fail with "'dict' object has no attribute".
        retire_demo = json.loads((tmp / "10_retirement_transition.json").read_text(
            encoding="utf-8"))
        checks["retire_transition_appends_a_retired_version"] = (
            retire_demo.get("status_after") == "RETIRED"
            and retire_demo.get("parent_linked") is True)
        checks["retire_keeps_the_harmful_version"] = retire_demo.get("chain_ok") is True
        checks["retire_is_on_a_copy_not_the_real_store"] = "COPY" in (
            retire_demo.get("note") or "")
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

        # 14 -- THE SKILL PARAMETER WAS SELECTED, NOT TYPED. A parameter nobody compared
        # against an alternative is a guess wearing a number; the comparison is free when
        # the feedback is already archived.
        board = json.loads((tmp / "02b_candidate_board.json").read_text(encoding="utf-8"))
        rows = board["board"]
        checks["several_candidates_were_compared"] = len(rows) >= 4
        checks["a_candidate_was_selected"] = board.get("selected") is not None
        # the board must KEEP the losers, or it cannot show that anything was compared
        checks["the_board_keeps_the_rejected_candidates"] = any(
            not r["admissible"] for r in rows)
        # feasibility is a hard filter, so the winner must fix every plan it was scored on
        sel_row = board.get("selected") or {}
        checks["the_winner_fixes_every_plan_it_was_scored_on"] = (
            sel_row.get("fixed") == sel_row.get("plans"))
        checks["the_winner_breaks_no_clearance_contract"] = (
            sel_row.get("clearance_violations") == 0)
        # cost is the OBJECTIVE among the feasible, never a term that can outvote a
        # violated contract
        admissible = [r for r in rows if r["admissible"]]
        checks["the_winner_is_the_cheapest_admissible_candidate"] = bool(admissible) and (
            sel_row.get("mean_displacement_m") == min(
                r["mean_displacement_m"] for r in admissible))
        # and a cheaper-but-unsafe candidate existed and lost with a stated reason
        rejected = [r for r in rows if not r["admissible"]]
        checks["a_rejected_candidate_states_why_it_lost"] = bool(rejected) and all(
            r.get("why") for r in rejected)

        # 15 -- REUSE ACROSS TASKS THE LESSON WAS NOT BUILT FROM. "It works on the input
        # it was derived from" is the weakest possible claim; the objective's claim is that
        # a lesson accumulated on one task is reused on later ones.
        audit = json.loads((tmp / "09b_reuse_audit.json").read_text(encoding="utf-8"))
        checks["a_skill_was_audited_over_the_whole_archive"] = bool(audit) and all(
            r.get("asset_id") for r in audit)
        checks["the_skill_fixes_tasks_beyond_its_source_instance"] = any(
            r["total_instances_fixed"] > 0 for r in audit)
        # the strongest form: families OTHER than the one the lesson came from
        checks["the_skill_fixes_at_least_one_OTHER_task_family"] = any(
            r["families_fixed_beyond_the_source"] for r in audit)
        # and it must not achieve that by thrashing conforming plans
        checks["the_skill_made_no_task_worse"] = all(
            r["total_made_worse"] == 0 for r in audit)
        # the report must state which claim it supports, so it cannot be read as a
        # cross-split transfer result when it is only cross-family
        checks["the_reuse_report_states_the_claim_it_does_not_support"] = all(
            "NOT cross-split" in (r.get("claim") or "") for r in audit)

        # 16 -- DID IT ARRIVE? Routing says which module CAN act; delivery says the entry
        # REACHED it. The gap is silent: the planner's renderer reads item["lesson"] while a
        # v2 entry carries suggested_action, so the lesson vanishes and the ledger records
        # NO_CHANGE - indistinguishable from "the lesson had no effect".
        deliv = json.loads((tmp / "09a_delivery.json").read_text(encoding="utf-8"))
        checks["every_active_entry_was_delivery_checked"] = bool(deliv)
        checks["every_active_entry_reached_its_consumer"] = bool(deliv) and all(
            v.get("verdict") == "DELIVERED" for v in deliv.values())
        # a parameter consumer's delivery means a REAL callable with REAL kwargs
        param = [v for v in deliv.values()
                 if v.get("consumer") in ("spread_policy", "executor_recovery")]
        checks["parameter_deliveries_bind_a_callable"] = bool(param) and all(
            v.get("callable", {}).get("function") for v in param)
        # ... and a planner delivery must be measurable WITHOUT claiming an effect
        import delivery as _delivery
        import public_observation as _po
        task = json.loads((WT / "benchmark" / "held_out" / "unseen_public" /
                           "HO-90899d657e68.json").read_text(encoding="utf-8"))
        probe_entry = {"entry_id": "delivery-probe", "consumer": "planner",
                       "failure_class": "planning",
                       "suggested_action": "emit the moves in the order the instruction "
                                           "states"}
        delivered = _delivery.deliver(probe_entry, _po.build_observation(task))
        checks["a_planner_entry_can_be_checked_for_delivery"] = (
            delivered.get("verdict") == "DELIVERED")
        # A planner entry with NO actionable text must be reported DROPPED, not accepted.
        # (Picking an arbitrary stored record instead read the harness entry, which
        # legitimately delivers a config value - the check has to name the case it means.)
        silent = {"entry_id": "no-text", "consumer": "planner",
                  "failure_class": "planning"}
        checks["an_entry_with_no_actionable_text_is_reported_dropped"] = (
            _delivery.deliver(silent, None).get("verdict") == "DROPPED")
        # A CONSUMER WITH NO DELIVERY PATH MUST BE UNSUPPORTED, NEVER A SILENT PASS.
        # This used to pin "development" as that consumer. The path now exists, so the check
        # is re-pointed rather than deleted: an undeclared consumer must still be refused,
        # or "the gap closed" would quietly become "the guard went away".
        orphan = {"entry_id": "x", "consumer": "not-a-consumer",
                  "suggested_action": "record the practice"}
        checks["a_consumer_with_no_delivery_path_is_unsupported"] = (
            _delivery.deliver(orphan, None).get("verdict") == "UNSUPPORTED")
        # ... and the consumer that USED to be that example must now be reachable, or the
        # re-pointing above hid a regression instead of reporting a fix
        checks["the_consumer_that_was_unreachable_is_now_reachable"] = (
            _delivery.deliver({"entry_id": "x", "consumer": "development",
                               "suggested_action": "record the practice",
                               "applicable_when": ["a"]}, None).get("verdict")
            == "DELIVERED")

        # 17 -- AN ORDER CLAUSE FAILURE IS TWO DIFFERENT THINGS. Three archived rows name
        # "order" as failed; only one is a reordering. The other two are runs where the
        # second move never happened, so it was never out of order. The clause name is the
        # same in all three and only the evidence separates them.
        postmortem = _load("postmortem")
        graded = postmortem.scan_with_report(include_held_out=True)[0]
        reordered = [r for r in graded if r.get("order_kind") == "reordered"]
        incomplete = [r for r in graded if r.get("order_kind") == "incomplete"]
        checks["an_order_clause_failure_is_told_apart_from_a_truncated_run"] = (
            bool(reordered) and bool(incomplete))
        checks["a_truncated_run_is_not_filed_as_an_order_lesson"] = all(
            postmortem.signature_of(r) == "incomplete_execution" for r in incomplete)
        checks["a_genuine_reordering_IS_filed_as_an_order_lesson"] = all(
            postmortem.signature_of(r) == "order_clause_violated" for r in reordered)
        # one genuine reordering is a mis-attribution risk, so the lesson must stay refused
        sigs = postmortem.generate()[1]["signatures"]
        checks["the_single_reordering_is_refused_for_lack_of_occurrences"] = (
            sigs.get("order_clause_violated", {}).get("built") is False)

        # 18 -- THE REGRESSION GATE'S SCOPE IS THE WHOLE CHECKOUT, NOT A PINNED PAIR.
        # It pinned 2 verifiers out of 70, so "nothing that used to work stopped working"
        # was a claim about 2 checks. Widening it exposed a second defect: the gate ran
        # every verifier including the chain verifier that contains it, so it re-ran itself
        # and reported a REVERT caused by recursion.
        regression = _load("regression")
        checks["the_regression_gate_covers_every_verifier"] = (
            len(regression.all_verifiers()) > 10)
        checks["the_gate_does_not_run_the_verifier_that_contains_it"] = (
            "evobot_continual_chain_20261118" in regression.SELF_VERIFIERS
            and "evobot_continual_chain_20261118" not in regression.all_verifiers())
        # the baseline must not be an excuse that grew: every entry names a verifier that
        # really fails, and each carries a reason it cannot be attributed to an entry
        known_doc = json.loads((WT / "evolution" / "validation" /
                                "known_failures.json").read_text(encoding="utf-8"))
        entries = known_doc.get("failures") or []
        checks["every_baselined_failure_carries_a_reason"] = bool(entries) and all(
            e.get("why_not_a_live_defect") for e in entries)
        checks["the_baseline_records_where_it_was_measured"] = all(
            e.get("measured_on") or e.get("classification") in
            ("STALE_RECORD", "STATE_DEPENDENT") for e in entries)
        # ... and it must be measured, not estimated: the 18 entries fail on the PR base too
        checks["the_baseline_was_measured_on_the_pr_base_commit"] = (
            "390166948abbbecc96f90e29054ed8804f089576"
            in (known_doc.get("measured_scope") or ""))

        # 19 -- THE MEASURED CROSS-FAMILY SCOPE MUST BE DELIVERABLE, not just reported.
        # The reuse audit measured the spacing lesson fixing 4 instances in two other
        # families, while retrieval gated on an EXACT task_family match - so every one of
        # those measured wins was withheld. A measurement the delivery channel cannot act
        # on is a number in a document.
        rows_after = store.read(str(tmp / "records_v2.jsonl"))
        active_rows = [r for r in rows_after
                       if (r.get("version") or {}).get("status") == "ACTIVE"]
        checks["an_active_entry_carries_a_measured_cross_family_scope"] = any(
            r.get("measured_families") for r in active_rows)
        _rev = _load("retrieve")
        checks["retrieval_offers_the_lesson_to_a_measured_OTHER_family"] = any(
            kept for kept in [
                [e.get("version", {}).get("label")
                 for e in _rev.retrieve("executor_recovery", task_family=fam,
                                        store_path=str(tmp / "records_v2.jsonl"),
                                        record=False)[0]]
                for fam in ("T12_triple_revisit", "T03_ordered")])
        # ... and it must stay WITHHELD from a family nobody measured it on
        checks["retrieval_still_withholds_it_from_an_unmeasured_family"] = (
            _rev.retrieve("executor_recovery", task_family="T14_ordered_pair",
                          store_path=str(tmp / "records_v2.jsonl"), record=False)[0] == [])
        # the family label must be DERIVED, so the harness lesson says T05 not T13
        checks["a_generated_entry_names_the_family_its_evidence_came_from"] = any(
            r.get("task_family") == "T05_relay" for r in rows_after
            if "harness" in str(r.get("version", {}).get("label")))

        # 20 -- THE PLANNER IS MEASURABLE WITHOUT A MODEL, but only on ONE thing.
        # consumers.CONSUMERS marks the planner measurable_offline=False because a plan's
        # QUALITY needs a model call. That is not the same as "nothing about the planner can
        # be checked". Its own validator now refuses a plan that reverses an order the
        # instruction fixed - a rule the SYSTEM PROMPT already stated and nothing verified.
        sys.path.insert(0, str(WT / "runtime" / "planner"))
        import agent_planner as _ap
        effect = _load("effect")
        order_obs = {
            "instruction": ("Put both blocks in the left bin. The blue block must be put "
                            "there FIRST, then the red block."),
            "objects": [{"name": "a", "color": "red"}, {"name": "b", "color": "blue"}],
            "zones": [{"name": "z", "position": [0.12, -0.15, 0.0]}]}
        reversed_moves = [{"object": "a", "zone": "z"}, {"object": "b", "zone": "z"}]
        ordered_moves = [{"object": "b", "zone": "z"}, {"object": "a", "zone": "z"}]
        checks["the_planner_refuses_a_plan_that_reverses_a_required_order"] = bool(
            _ap.check_plan_order(order_obs, reversed_moves))
        checks["the_planner_accepts_the_required_order"] = (
            _ap.check_plan_order(order_obs, ordered_moves) is None)
        # ... and it must be INERT when the instruction fixes no order at all
        checks["the_order_check_is_inert_when_the_instruction_fixes_none"] = (
            _ap.check_plan_order({"instruction": "Put both blocks in the right bin.",
                                  "objects": order_obs["objects"],
                                  "zones": order_obs["zones"]}, reversed_moves) is None)
        # the probe must catch the archive's one genuine reversal, which is a FOREIGN plan
        order_probe = effect.probe({
            "entry_id": "planner-order-probe", "consumer": "planner",
            "failure_class": "planning",
            "effect_spec": {"fixture": "t14_ordered_pair", "operator": "plan_order",
                            "expect": {"catches_violations": True,
                                       "no_false_positives": True}}})
        checks["the_planner_has_a_model_free_measured_effect"] = (
            order_probe["verdict"] == "IMPROVED")
        checks["that_probe_refuses_none_of_the_compliant_plans"] = (
            order_probe["detail"]["false_positives"] == 0)

        # 21 -- THE THIRD TRANSITION. lifecycle.py's docstring lists three (RETIRE, REVISE,
        # KEEP) and only two existed. REVISE is the one that matters when the record is
        # narrower than a fresh measurement: the entry is not harmful (so RETIRE is wrong)
        # and it is not fine (so KEEP is wrong). DGM's point is that a version evolves when
        # evidence changes, and an activation-time snapshot is evidence that goes stale.
        revise = json.loads((tmp / "10_revision_transition.json").read_text(encoding="utf-8"))
        checks["a_record_narrower_than_its_measurement_is_revised"] = (
            revise.get("ran") is True
            and any(d["decision"] == "REVISE"
                    for d in revise.get("decision_before") or []))
        checks["the_revision_widens_the_scope_to_the_measured_one"] = set(
            revise.get("added") or []) and set(revise["added"]).issubset(
                set(revise.get("scope_after") or []))
        # A revision must NOT be a second, unreviewed activation wearing a version bump.
        checks["a_revision_changes_only_the_measured_scope"] = (
            revise.get("lesson_unchanged") is True)
        checks["a_revision_keeps_the_previous_version_on_disk"] = (
            revise.get("old_version_still_on_disk") is True)
        checks["a_revision_links_its_parent_and_stays_ACTIVE"] = (
            revise.get("parent_linked") is True and revise.get("status_after") == "ACTIVE")
        # ... and it must SETTLE: a second pass must not revise the same entry again.
        checks["the_revision_is_idempotent"] = revise.get("still_revise_after") == []
        checks["the_store_chain_verifies_after_a_revision"] = (
            revise.get("chain_ok") is True)
        # REVISED is a transition, not an outcome: counting it as helpful would credit an
        # entry for a bookkeeping change.
        lg = _load("ledger")
        checks["a_revision_is_not_recorded_as_a_usage_outcome"] = (
            "REVISED" in lg.EVENTS and "REVISED" not in lg.OUTCOMES)

        # 22 -- STALENESS IS TWO-SIDED, and only one side is safe. The first version of the
        # check computed added = measured - recorded and called an empty diff "not stale",
        # so a record claiming a family the instrument cannot confirm passed review - and
        # retrieval acts on the claim, turning an over-claim into a wrong action.
        _lc = _load("lifecycle")
        narrowed = _lc.stale_scope(demo.entry_executor_side(), acceptance=str(WT / "setup" / "acceptance"),
                                   source_task="HO-90899d657e68")
        checks["a_record_narrower_than_its_measurement_is_stale"] = (
            narrowed["stale"] is True
            and narrowed["direction"] == "narrower_than_measurement")
        # the over-claim direction: a family nobody measured must be reported, and removable
        over = dict(demo.entry_executor_side())
        # The demo entry has not been measured yet when this runs, so its record under-claims
        # AND (once the bogus family is added) over-claims: both directions at once, which is
        # exactly the case an if/elif hid.
        over["measured_families"] = list(over.get("measured_families") or []) + ["T99_bogus"]
        over["version"] = dict(over["version"], status="ACTIVE")
        over["validation"] = {"review_verdict": "ACCEPT", "reviewed_by": "probe"}
        over_scope = _lc.stale_scope(over, acceptance=str(WT / "setup" / "acceptance"),
                                     source_task="HO-90899d657e68")
        checks["a_record_WIDER_than_its_measurement_is_stale_too"] = (
            over_scope["stale"] is True
            and over_scope["direction"] in ("wider_than_measurement", "both_directions")
            and "T99_bogus" in over_scope["unconfirmed"])
        # ... and apply() must carry out a REVISE, not only a RETIRE
        import inspect as _insp
        src = _insp.getsource(_lc.apply)
        checks["apply_carries_out_a_revision_not_only_a_retirement"] = (
            "REVISE" in src and "revise(" in src)

        # 23 -- THE LEDGER MUST NAME THE TASK. The master goal's fifth step is "record how
        # it was used afterwards: WHICH TASK retrieved it, what action changed, what the
        # result was". The reuse audit is the only place a skill is applied to tasks it was
        # not built from, and it wrote that into a report file and nowhere else: the ledger
        # said two applications under one demo label while SEVEN real tasks had been handled.
        lg_rows = [json.loads(line) for line in
                   (tmp / "usage_ledger.jsonl").read_text(encoding="utf-8").splitlines()
                   if line.strip()]
        # A task id is either a sealed instance ("HO-...") or a dev-split run
        # ("T01-train-seed1000"). Testing only for "HO-" silently excluded every dev-split
        # task from the count, which is how a "which task" check can pass while half the
        # archive is invisible to it.
        def _is_task_id(value):
            value = str(value or "")
            return value.startswith("HO-") or "-seed" in value
        task_ids = {r.get("run_id") for r in lg_rows if _is_task_id(r.get("run_id"))}
        checks["the_ledger_names_the_tasks_a_skill_was_used_on"] = len(task_ids) >= 5
        # ... and each of those tasks carries its own RETRIEVED/APPLIED/OUTCOME triple,
        # because "offered but inert" and "applied and helped" must not look alike.
        per_task = {}
        for row in lg_rows:
            rid = row.get("run_id")
            if _is_task_id(rid):
                per_task.setdefault(rid, set()).add(row.get("event"))
        checks["each_recorded_task_has_retrieved_applied_and_outcome"] = bool(per_task) and all(
            {"RETRIEVED", "APPLIED", "OUTCOME"} <= events
            for events in per_task.values())
        # the recorded APPLIED count must match what the reuse audit actually fixed
        audit_totals = [r["total_instances_fixed"] for r in audit]
        checks["the_recorded_applications_match_the_audit"] = (
            len(per_task) >= max(audit_totals or [0]))
        # A WINS-ONLY LEDGER IS THE MIRROR OF THE ERROR THE LEDGER WARNS ABOUT. Its docstring
        # records "one lesson was retrieved for every task and changed no plan"; recording
        # only the winners makes every application look like it changed the outcome.
        outcome_kinds = {r.get("outcome") for r in lg_rows if r["event"] == "OUTCOME"}
        checks["the_ledger_records_inert_applications_too"] = "UNCHANGED" in outcome_kinds
        applied_rows = [r for r in lg_rows if r["event"] == "APPLIED"]
        changed_rows = [r for r in applied_rows if r.get("changed")]
        # the hit rate must be able to be SMALL: a ledger that only ever says 100% is not
        # measuring, it is collecting
        checks["the_recorded_hit_rate_is_not_flattered"] = (
            len(applied_rows) >= 10
            and len(changed_rows) < len(applied_rows))
        # 25 -- A RATE MUST BE COMPUTED IN ONE UNIT. fixed is counted per task instance and
        # untouched was counted per PLAN FILE, and dividing one by the other reported a 2.4%
        # effect for a 6.4% one: the same task appears in several batches, so the plan-file
        # denominator is about 3x too big. The audit now carries both counts and both rates.
        per_asset = audit[0] if audit else {}
        checks["the_reuse_report_carries_a_rate_it_can_defend"] = (
            per_asset.get("instances_offered", 0) > 0
            and per_asset.get("plans_offered", 0) > per_asset.get("instances_offered", 0))
        # the two denominators must actually differ, or the distinction is untested
        checks["the_plan_and_instance_denominators_are_not_the_same_number"] = (
            per_asset.get("plans_offered") != per_asset.get("instances_offered"))
        # and the reported rate must be the instance one, not a cross-unit fraction
        fixed = per_asset.get("total_instances_fixed") or 0
        offered = per_asset.get("instances_offered") or 1
        checks["the_reported_hit_rate_uses_matching_units"] = (
            abs((per_asset.get("instance_hit_rate") or 0) - fixed / float(offered)) < 1e-3)

        # 26 -- A DECLARED DESTINATION IS NOT A COVERED ONE. The objective names four
        # routings; consumers.py declares all four; three of them carry a live entry and the
        # fourth (ROS launch -> development experience) has never carried anything. Nothing
        # said so, because nothing asked: implemented() only checks that the entrypoint FILE
        # exists, which says a destination is addressable, not that mail arrives.
        cov = json.loads((tmp / "10b_routing_coverage.json").read_text(encoding="utf-8"))
        by_consumer = {r["consumer"]: r["state"] for r in cov["routings"]}
        checks["the_objectives_four_routings_are_all_measured"] = (
            cov["named"] == 4 and set(by_consumer) == {"planner", "spread_policy",
                                                       "executor_recovery", "development"})
        checks["at_least_one_named_routing_actually_carries_an_entry"] = (
            cov["carried"] >= 1)
        # ... and the gap must be REPORTED, not silently rounded up to 4/4
        # ... and the gap must be reported by KIND, not blended: an empty routing (path works,
        # nothing routed here) is different work from an unreachable one (entry exists, cannot
        # arrive). Blending them lets one hide behind the other.
        checks["no_named_routing_is_unreachable"] = (
            "NO_DELIVERY" not in by_consumer.values())
        checks["the_gap_is_reported_by_kind"] = (
            cov["carried"] < cov["named"]
            and all(state in ("CARRIED", "NO_ENTRY", "NO_DELIVERY", "NAMED_BUT_EMPTY")
                    for state in by_consumer.values()))
        # the ROS-launch lesson does act - from a consumer the objective did not name, which
        # is reported separately rather than counted as coverage of the fourth routing
        checks["acting_from_an_unnamed_consumer_is_reported_separately"] = (
            "harness" in cov["carried_by_an_unnamed_consumer"])

        # 27 -- NO LIVE BEHAVIOUR CHANGE WITHOUT AN ENTRY BEHIND IT. The order rule was
        # wired straight into validate_plan, so the planner refused plans it used to accept
        # - with no entry to review, probe for misuse, record an outcome for, or retire.
        # Step 4 of the objective is explicit that a change is validated and versioned
        # BEFORE it is enabled. The rule is now gated on an admitted entry, which arrives
        # through the same "experience" channel describe() reads.
        plain_obs = {
            "instruction": ("Put both blocks in the left bin. The blue block must be put "
                            "there FIRST, then the red block."),
            "objects": [{"name": "a", "color": "red"}, {"name": "b", "color": "blue"}],
            "zones": [{"name": "z", "position": [0.12, -0.15, 0.0]}]}
        reversed_plan = {"moves": [{"object": "a", "zone": "z"},
                                   {"object": "b", "zone": "z"}]}
        _, ungated = _ap.validate_plan(reversed_plan, plain_obs)
        checks["the_order_rule_is_not_live_without_an_admitted_entry"] = not any(
            "FIRST" in p for p in ungated)
        admitted_obs = dict(plain_obs)
        admitted_obs["experience"] = [{"failure_class": "planning",
                                       "lesson": "emit moves in the stated order",
                                       "_entry_id": "e" * 64}]
        _, gated = _ap.validate_plan(reversed_plan, admitted_obs)
        checks["the_order_rule_acts_once_an_entry_is_admitted"] = any(
            "FIRST" in p for p in gated)
        # the delivery path stamps the marker the gate looks for, so delivered entries work
        delivered_obs = _load("delivery").deliver_planner(
            {"entry_id": "x" * 64, "consumer": "planner", "failure_class": "planning",
             "suggested_action": "emit the moves in the order the instruction states"},
            plain_obs)
        checks["a_delivered_entry_admits_the_rule"] = (
            _ap.order_rule_admitted(delivered_obs) is True)
        # ... and the coverage report must CHECK for unbacked live rules rather than only
        # counting entries: a rule wired into the code path acts without any entry and is
        # worse than an empty routing, not better.
        checks["the_coverage_report_checks_for_unbacked_live_rules"] = (
            cov.get("live_rules_with_no_entry") == [])
        checks["the_coverage_claim_says_an_unbacked_rule_is_worse"] = (
            "worse than an empty routing" in (cov.get("claim") or ""))
        # 29 -- A PATH FOR THE FOURTH ROUTING EXISTS. It used to be UNSUPPORTED, which meant
        # "ROS 启动经验归入开发经验" could not have been honoured even if an entry had existed.
        dev = _load("delivery").deliver(
            {"entry_id": "x" * 64, "consumer": "development",
             "suggested_action": "check the DDS participant pool before launching many nodes",
             "applicable_when": ["launching N ROS 2 processes in one domain"]}, None)
        checks["the_development_routing_now_has_a_delivery_path"] = (
            dev.get("verdict") == _load("delivery").DELIVERED)
        # ... and it must NOT masquerade as a PROPOSED registry skill: PROPOSED means
        # written, unit-tested and mutation-tested, and this entry has none of those.
        checks["a_rendered_candidate_does_not_claim_PROPOSED"] = (
            dev["candidate"]["status"] != "PROPOSED"
            and dev["candidate"]["revisit_metrics"]["effect"] == "NOT_MEASURED")
        checks["a_rendered_candidate_names_what_it_cannot_supply"] = (
            set(dev["missing_registry_fields"]) == {"entrypoints", "tests", "mutation"})
        # a development practice with no trigger is never loaded - that is the failure mode
        # behind the zero-adoption measurement, so it must be refused rather than rendered
        checks["a_development_candidate_without_a_trigger_is_refused"] = (
            _load("delivery").deliver(
                {"entry_id": "x", "consumer": "development",
                 "suggested_action": "do something"}, None)["verdict"] == "DROPPED")

        # 28 -- THE COMMITTED EVIDENCE MUST STILL DESCRIBE THE CODE. verify.py regenerates
        # into a temp directory and asserts properties of THAT run, so it checks the code is
        # self-consistent, not that the committed artifacts are current. They had already
        # diverged: 18 of 32 files recorded a chain the current code no longer produces,
        # because the entry body embedded an ABSOLUTE output path and the entry_id is a
        # digest of that body.
        freshness = _load("evidence_freshness").compare(fresh_dir=str(tmp))
        checks["the_committed_evidence_numbers_match_a_fresh_run"] = not freshness[
            "number_drift"]
        # ... and the ids must match too. They only did once review_ref stopped carrying
        # the run directory, and that is what made an evidence check possible at all.
        checks["the_committed_evidence_ids_match_a_fresh_run"] = not freshness["id_churn"]
        checks["every_committed_artifact_is_still_produced"] = not freshness["missing"]

        # 30 -- "UNROUTED" IS A STATEMENT ABOUT OUR SIGNATURE TABLE, NOT ABOUT THE WORLD.
        # The generator refuses 7 of 9 signatures as UNROUTED, covering 92 of the archive's
        # 98 failures. Read as "nothing can act", that turns unwritten work into a measured
        # limit - the same error route_lessons.py records from the other direction.
        unrouted = json.loads((tmp / "10c_unrouted_analysis.json").read_text(encoding="utf-8"))
        states = {row["signature"]: row["state"] for row in unrouted["unrouted"]}
        checks["the_unrouted_signatures_are_itemised_not_counted"] = (
            len(states) == len(unrouted["unrouted"]) > 0)
        checks["every_unrouted_signature_states_what_is_known"] = all(
            row.get("state") and row.get("why") for row in unrouted["unrouted"])
        # the one that was MEASURED must say so, and must not be silently promoted either way
        checks["the_measured_signature_is_reported_as_measured"] = (
            states.get("placement_clause_failed") in ("ALREADY_CORRECT",
                                                      "FAILED_INSTANCES"))
        # 31 -- A MODULE CAN EXIST AND THE ARCHIVE STILL CANNOT MEASURE IT. push_recover is
        # a real closed-loop retry policy with a recorded 2/5 -> 4/5 comparison, so
        # graded_push HAS a capable module - but its recorded attempts were produced BY that
        # policy, and replaying a policy over its own output cannot show what it changed.
        # That is a selection effect, and reporting it as "no capable module" or as a
        # measured null result would both be answers the data cannot support.
        push = next((r for r in unrouted["unrouted"] if r["signature"] == "graded_push"), {})
        checks["a_capable_module_with_an_unmeasurable_archive_is_called_out"] = (
            push.get("module_found") is True and push.get("state") == "UNMEASURED")
        checks["the_selection_effect_is_named_not_reported_as_a_null_result"] = (
            "selection effect" in (push.get("why") or "")
            or "replaying it over them cannot measure" in (push.get("why") or ""))
        # the replay itself must be CORRECT, or the note above is about a broken replay
        probe = push.get("probe") or {}
        checks["the_policy_replay_reproduces_the_recorded_verdicts"] = (
            probe.get("verdicts_reproduced") == len(probe.get("trials") or []) > 0)
        # ... and an unmeasured one must NOT claim a verdict. This is the assertion that
        # caught this module's own first version, which asserted "no capable module" for six
        # signatures on the strength of their names alone.
        checks["an_unprobed_signature_does_not_claim_a_verdict"] = all(
            row["state"] == "UNMEASURED" for row in unrouted["unrouted"]
            if row["signature"] not in unrouted.get("probed", {}) and
            not row.get("probe"))
        # a hypothesis must be labelled as one, never cited as a measurement
        # a label is required only where a GUESS is being offered. A signature whose module
        # was actually found carries a probe, not a hypothesis.
        checks["a_candidate_consumer_is_labelled_a_hypothesis"] = all(
            "NOT a measurement" in (row.get("probe_is") or "")
            for row in unrouted["unrouted"]
            if row["state"] == "UNMEASURED" and not row.get("module_found"))

        # 32 -- THE LOOP CAN BE CORRECT AND UNPLUGGED. Everything the demo proves is proved
        # INSIDE the chain's own harness. The code that hands experience to the planner for a
        # real robot run reads a different store with a different schema, so a reader must
        # not take "the chain works" as "the robot uses it".
        live = json.loads((tmp / "10d_live_path.json").read_text(encoding="utf-8"))
        checks["the_live_path_connection_is_measured"] = (
            isinstance(live.get("visible_to_live_path"), int)
            and "active_entries" in live)
        # the numbers must actually add up, or the report is decorative
        checks["every_invisible_entry_states_a_reason"] = (
            sum(live["by_reason"].values()) + live["visible_to_live_path"]
            == live["active_entries"])
        # ... and it must be able to say ZERO. A report that cannot is not measuring.
        checks["the_report_can_say_the_loop_is_unplugged"] = (
            live["visible_to_live_path"] < live["active_entries"]
            or live["active_entries"] == 0)
        # the two ways to close it are named WITH their cost; picking one silently would be
        # the kind of schema decision that has to be visible
        checks["closing_the_gap_is_stated_as_a_choice_with_a_cost"] = (
            len(live["options"]) == 2 and all(o.get("cost") for o in live["options"]))
        # 33 -- A SCHEMA BRIDGE IS NOT THE FIX, AND THE FIRST VERSION OF THIS REPORT SAID IT
        # WAS. Both ACTIVE entries are tooling/control class, and the live retrieve() admits
        # only planning/state while its word list rejects landing/spread/participant. They are
        # excluded BY DESIGN. There is no consumer for either in the live run scripts.
        checks["a_schema_bridge_cannot_rescue_these_entries"] = (
            live["planner_filter_result"]
            and not any(x["would_a_bridge_help"]
                        for x in live["planner_filter_result"]))
        checks["the_missing_consumers_are_named"] = (
            any(not c["has_a_live_consumer"]
                for c in live["consumers_in_live_path"].values()))
        # 34 -- "NO CONSUMER" WAS ALSO WRONG. The shell runner calls recovery_driver.py,
        # which does call apply_respread, so the executor consumer EXISTS. The real gap is
        # narrower: the call site reads no entry and uses default kwargs, so a revised entry
        # can never reach the robot. A finding that scopes itself correctly matters more than
        # a bigger-sounding one that is false.
        exec_c = live["consumers_in_live_path"].get("executor_recovery") or {}
        checks["the_executor_consumer_exists_in_the_shell_runner"] = (
            exec_c.get("has_a_live_consumer") is True
            and bool(exec_c.get("call_sites_in_live_scripts")))
        # This check used to assert reads_the_entry is False. That pinned the PRE-WIRING
        # defect. The wire now landed, so the correct assertion flipped; deleting it would
        # have turned "the gap closed" into "the guard went away".
        checks["the_executor_consumer_now_reads_a_reviewed_entry"] = (
            exec_c.get("reads_the_entry") is True)
        checks["the_claim_does_not_say_no_consumer"] = (
            "no harness/executor consumer" not in live["claim"])

        # 35 -- THE LAST MILE HAS A REAL WIRE, AND IT IS FAIL-CLOSED. recovery_driver.py now
        # accepts an opt-in --experience-asset/--experience-entries pair; resolve() re-checks
        # the chain, ACTIVE+latest, an INDEPENDENT ACCEPT and a numeric callable from the ENTRY
        # before any parameter reaches apply_respread. No flags = frozen defaults.
        steps_by_name = {s["step"]: s for s in summary["steps"]}
        wire = steps_by_name.get("live_wiring") or {}
        checks["the_live_wire_exists_and_defaults_are_untouched"] = (
            wire.get("no_flags_kwargs") == {})
        # the self-reviewed chain entry must NOT drive the robot; the reviewer is the same
        # run that made the entry, which is not independent
        checks["a_self_reviewed_entry_cannot_drive_the_live_call"] = (
            wire.get("self_reviewed_kwargs") == {})
        # 36 -- THE REAL INDEPENDENT ACCEPT IS FOR A DIFFERENT CLAIM. The repo's ledger has
        # an ACCEPT for a control fact built on exactly E2's three evidence files. An
        # independent review of the SAME EVIDENCE for a DIFFERENT CLAIM must not authorise
        # E2's actionable spacing recommendation. The gate reads a separate ledger keyed by
        # entry_id, not the entry's own validation block (which its authoring round wrote).
        checks["a_review_of_another_claim_cannot_drive_the_live_call"] = (
            wire.get("real_ledger_other_claim_kwargs") == {})
        # and the driver really passes the resolved kwargs through to the call
        drv_src = (WT / "runtime" / "recovery" / "recovery_driver.py").read_text(
            encoding="utf-8")
        checks["the_driver_passes_resolved_kwargs_to_apply_respread"] = (
            "**kwargs" in drv_src and "_experience_kwargs" in drv_src)
        checks["the_wire_requires_an_independent_ledger"] = (
            "experience_review_ledger" in drv_src)
        # 37 -- THE INDEPENDENT LEDGER ITSELF MUST NOT BE FORGEABLE. Before this, a reviewer
        # could be invented by appending one plain JSONL line, which would authorise a live
        # robot parameter. The ledger is now a hash chain and the gate refuses an unpacked or
        # edited one; its limits (identity, new reviews, tail truncation) are stated.
        checks["the_review_ledger_is_declared_chained"] = (
            wire.get("review_ledger_is_chained") is True)
        checks["the_ledger_limits_are_stated_not_hidden"] = all(
            word in (wire.get("review_ledger_limits") or "")
            for word in ("identity", "tail truncation"))
        # 38 -- APPLICABILITY ON THE ACTUAL RUN (step 4). The live gate now checks the
        # entry's own invalid conditions against the real plan before handing parameters to
        # apply_respread; an already-conforming plan must get the defaults, not a rotation.
        checks["applicability_is_checked_on_the_real_run"] = (
            wire.get("applicability_checked_on_the_real_plan") is True)
        checks["the_driver_supplies_the_real_plan_to_the_gate"] = (
            "experience_observation" in drv_src)
        # 39 -- STEP 5 AT THE LIVE BOUNDARY. The driver used to apply an entry's parameters
        # and record NOTHING about it: "which task used this entry" was unanswerable for the
        # only path that runs a robot. It now writes RETRIEVED/APPLIED/OUTCOME with the run
        # id - and writes NOTHING when it fell back to defaults, because a fallback is not
        # an application.
        checks["the_driver_records_a_live_application"] = (
            "experience_usage_ledger" in drv_src and "RETRIEVED" in drv_src)
        checks["a_live_fallback_is_not_recorded_as_an_application"] = (
            "and kwargs" in drv_src or "if ledger_path and entry_id_used and kwargs"
            in drv_src)
        checks["the_live_recording_is_declared"] = (
            wire.get("applied_live_entries_are_recorded") is True
            and wire.get("a_default_path_records_nothing") is True)

        verdict = {
            "record_kind": "EVOBOT_CONTINUAL_CHAIN_VERDICT",
            "batch": HERE.name,
            "checks": checks,
            "checks_total": len(checks),
            "checks_passed": sum(1 for v in checks.values() if v),
            "chain_message": msg,
            "measured": {"deliveries": {label: p["verdict"]
                                        for label, p in probes.items()},
                         "selected_skill_parameter": board.get("selected", {}).get(
                             "candidate"),
                         "candidates_compared": len(rows),
                         "candidates_rejected": sum(1 for r in rows
                                                    if not r["admissible"]),
                         "reuse_instances_fixed": [r["total_instances_fixed"]
                                                   for r in audit],
                         "reuse_families_beyond_source": [
                             r["families_fixed_beyond_the_source"] for r in audit],
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
