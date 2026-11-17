# Continual chain — one experience entry, end to end (2026-11-18)

**Level reached: Implemented + Unit Tested + offline chain measurement.**
**NOT Simulation Tested. No new robot run was made this round.**

Re-run: `python3 setup/acceptance/evobot_continual_chain_20261118/verify.py`
Chain demo: `python3 evolution/experience/demo_continual.py`

---

## What this batch is

The master goal's P4 question is whether an experience can be
**acquired → stored → retrieved → applied → measured**. Prior rounds built the storage
half and then measured a null result: two independent B/C experiments produced
byte-identical plans, and an audit found the mechanism — the lessons were about landing
coordinates and the planner has no field to put one in.

This batch closes the other half and, while doing it, reproduces the same defect one
layer deeper. One lesson was offered to two consumers of the same stack:

| delivery address | code path | measured result |
| --- | --- | --- |
| planner-side spread policy | `runtime/planner/spread_destinations.py::spread` | **NO_CHANGE** — groups stages by EXACT equal pose; the plan builder had already offset the two stages by 56 mm, so there is no group to spread |
| executor-side recovery | `runtime/recovery/recover.py::apply_respread` | **CHANGED** — clusters by DISTANCE, finds the pair, widens separation 56 mm → 90 mm, and (after the fix in this batch) keeps clearance 81.4 mm > 50 mm contract |

So "experience has no effect" can be true of one address and false of another **in the
same repository, on the same lesson, on the same archived input**. Routing by declared
capability is what makes that visible instead of leaving it to an audit.

---

## The chain the verifier re-runs

1. **measured failure** — read from `evobot_recover_n6_20261111/runs/HO-90899d657e68`
   (err 61, "state drift or occupied destination before target_box_b-1")
2. **entry** — v2 schema, seven master-goal fields, consumer chosen by capability
3. **effect** — `effect_spec` EXECUTED against the archived plan, twice, with the current
   parameter and with the proposed one; the verdict is computed from the two outputs
4. **curation** — duplicate refused; conflict refused; a same-condition/different-parameter
   entry would supersede and merge evidence
5. **retrieval** — before review: **0 kept, 2 refused**; after independent ACCEPT: exactly 1
5. **activation** — APPENDS the reviewed successor; the candidate stays on disk; the hash
   chain still verifies ("chain intact (4 records)")
6. **apply + outcome** — APPLIED records the measured delta, OUTCOME records the verdict,
   and the entry's state is derived from those events: `used_helpful`
7. **regression gate** — activation requires `KEEP` from the pinned verifier subset, not
   only an ACCEPT review. `REVERT` and `UNKNOWN` both refuse. The verdict is written into
   the activated record, so "it passed regression" is re-checkable.
8. **skill asset** — the ACTIVE entry compiles into a **callable** asset bound to
   `recover.apply_respread` with fixed parameters and a three-item guard. The REJECTED
   delivery compiles nothing: an asset can be called, so only a reviewed,
   regression-passed entry may become one.

9. **misuse check** — every declared invalid condition is executed as a real scenario;
   the consumer must refuse or stay inert. **UNPROBED is refused, not passed**: a
   disclaimer nobody tested is the same thing as a gate nobody runs.
10. **lifecycle** — the ledger's verdict becomes an action. A harmful entry is RETIRED by
   appending a successor (the harmful version stays on disk), and retrieval stops serving
   it. Note: nothing in this batch made a run worse, so the transition is demonstrated on
   a **copy** with a synthetic WORSE event; the real store is untouched.

11. **entry generation** — the first entry is not written in the demo script; it is
   produced by `postmortem.py` from 51 archived failures. The generator emitted one entry
   (`occupied_destination`, 5 occurrences) and **refused** the largest cluster
   (`unconfirmed_native`, 46 occurrences) as UNROUTED: this stack has no callable function
   that resumes from a measured state, so the knowledge has nowhere to act.

`verify.py` asserts **40 checks**, including that both gates really ran, that the asset
binds to a function that exists, that the rejected delivery produced no asset, that
retirement still lets retrieval see nothing, that **no generated record was ever ACCEPTed
without a named reviewer**, and that **every entry declares which split its evidence came
from** — with the dev split tried first and reported as producing nothing.

---

## The source change this batch made, and why it is bounded

`recover.apply_respread` always walked the +x axis. On this plan that put the second
landing point **46 mm** from box_b's declared spawn — below the 50 mm clearance contract —
so the retry was refused as "occupied destination" for the third time, now from the
recovery path rather than the planner.

The change:
- the axis is CHOSEN by which one keeps the largest margin to the other objects;
- if neither axis keeps the clearance contract, it **refuses** rather than emitting an
  unholdable plan;
- with no avoid list the behaviour is **byte-identical** to before, so every existing
  caller and test is unaffected.

It touches no evaluator, tolerance, threshold or held-out answer. 11/11
`benchmark/tests/test_recovery_driver.py` tests still pass.

---

## Honest limits (do not quote past these)

0. **THE EVIDENCE IS HELD-OUT, SO THIS IS NOT A GENERALIZATION RESULT.** Every entry in
   this batch — both hand-written ones and the generated one — reads
   `HO-90899d657e68`, which lives in `benchmark/held_out/unseen_public`. The T12/T13 task
   families exist **only** in the held-out set; `benchmark/tasks/train` and `.../val`
   contain T01–T06 and no T13 at all. So there is no development-split T13 to learn from,
   and the chain learned from the set it would be measured on. It demonstrates a
   **mechanism**; it does not show that the agent generalizes. Every entry carries
   `evidence.evidence_split == "held_out"` and the verifier asserts it.

   The generator now refuses held-out evidence by default (two independent rules: the
   batch's `evidence_index` rung says "Generalization Tested", and the run cites an
   instance in the current sealed set). Its honest dev-split output is **zero entries**,
   and the report says so.
1. The review artifact is written by a **separate step of the same run**, not by an
   outside reviewer. The schema forbids an AGENT_GENERATED entry from carrying its own
   ACCEPT, but a machine step is still not a person.
2. Every outcome is the effect_spec's expectation met on an **archived** input. No
   Gazebo window and no real robot run were made this round.
3. The **planner consumer is not measurable offline**: a prompt-level delivery needs a
   model call. It is reported `UNMEASURED`, never scored as no-effect.
4. The entry that is ACTIVE here is about **one** task family (T13). Nothing in this
   batch shows transfer to a different task type.
5. `used_helpful` means: applied once, measured once, expectation met on the archive.
   It is not a success rate, and n=1.
6. The regression gate runs a **pinned two-verifier subset** per consumer, not all 109.
   It can miss a regression outside that subset; the subset is written down so the gap is
   visible rather than implied to be complete.
7. The skill asset binds parameters to an **already-tested** function. It generates no
   robot code, and nothing here shows an asset can be *composed* into a new task.
8. **RETIRE has never fired on real evidence.** No run in this batch made anything worse,
   so the transition is shown on a copy with a synthetic WORSE outcome. A retirement
   driven by a real regression is still missing.
9. The misuse probes cover the spacing and respread consumers only (6 probes). The
   harness and development consumers have none, so their entries would report UNPROBED.
10. **Entry generation is automatic but narrow.** The generator reads archived failures
    and emits candidates, but the signature→consumer mapping table is hand-maintained,
    and 46 of 51 archived failures fall outside it (UNROUTED, honestly reported rather
    than forced into a spec that measures a different function).

---

## Why the delivery-address fix is the interesting result

The prior round's conclusion was "the planner never errs, so the retrieval set is empty".
This batch shows the retrieval set was empty **for the planner**, and that the same lesson
has a real effect at the executor. A single delivery address turns a mechanism into a
null result; the routing table makes the address an explicit, testable property of the
entry rather than a guess made by keyword matching.
