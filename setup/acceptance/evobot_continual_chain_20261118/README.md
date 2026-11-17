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

11. **entry generation** — the harness entry is not written in the demo script; it is
   produced by `postmortem.py` from the archived HARNESS-layer failures. The generator
   emits `harness_dds_exhaustion` (5 occurrences, development split) and **refuses** the
   largest cluster (`unconfirmed_native`, 31 occurrences) as UNROUTED: this stack has no
   callable function that resumes from a measured state.
12. **harness delivery is measurable.** It was marked `measurable_offline=False` with the
   reason "a config change cannot be measured". A config change IS measurable: against the
   archived before/after batch pair (harness failures 2/7 → 0/7) and against the live
   contract (participant pool 120 ≥ 6 launch nodes).

13. **the misuse check found a real defect this round.** `apply_respread` widened every
    cluster within `cluster_m`, including clusters already at the contract — and because
    the axis is chosen by margin it ROTATED them rather than rewriting them. On the
    archive that touched 127 plans and **94 needed no change**, displaced 64 mm in the T03
    case. Fixed by skipping a group whose current separation already meets `spread_step`;
    the condition and its probe (`spacing.already_satisfied`) now guard the regression.

14. **the skill parameter is selected, not typed.** `candidate_search.py` compares 6
    candidates over the archive under a hard feasibility filter (fix every plan, break no
    clearance contract, never reduce separation) with cost as the objective among the
    feasible. The cheapest-by-design candidate — `minimal_move`, 17 mm of displacement
    instead of 53 mm on the two-stage case it was written for — is **rejected**: it puts a
    landing 46.1 mm from box_b, which is the 2026-11-18 defect. Judging it by its cost on
    the case it was designed for would have shipped it. Rejected candidates stay on the
    board with their numbers and the reason.

15. **reuse is measured on tasks the skill was NOT built from.** `reuse.py` runs the
    compiled asset over the whole archive and reports per task family: newly fixed,
    untouched, made worse, refused. The spacing lesson was learned from a **T13** failure
    and also fixes **T12** (3 instances) and **T03** (1) — 7 distinct instances across 3
    families, **0 made worse, and no conforming plan touched**. Instances are counted once,
    not once per plan file: the same instance appears in several batches and file counting
    would inflate the result fourfold. "Untouched" is a pass condition, not a miss — an
    asset that disturbs a conforming plan is a defect, which is how the 2026-11-18
    rotation bug was found. The report states the claim it does **not** support: every
    instance in this archive is held-out, so this is cross-**family** reuse, **not**
    cross-split transfer.

16. **delivery is measured, and it is not the same as effect.** `consumers.py` says which
    module CAN act on an entry; it does not say the entry REACHED it. The gap was silent:
    the planner's prompt renderer reads `item["lesson"]` while a v2 entry carries
    `suggested_action`, so the lesson rendered as an empty bullet, the plan did not
    change, and the ledger recorded `NO_CHANGE` — indistinguishable from *"the lesson had
    no effect"*. `delivery.py` renders each entry into the shape its consumer actually
    reads and reports DELIVERED / DROPPED / UNSUPPORTED — all three deterministic. The
    planner's **effect** still reports `UNMEASURED` (a plan-level change needs a model
    call); what changed is that it can now say *"delivered, effect not measured"* instead of
    *"consumer not measurable"*.

17. **"order clause failed" is two different things.** Three archived rows name `order` as
    the failed clause; **only one is a reordering.** The other two are runs where the
    second move never happened — observed is a strict **prefix** of required — so it was
    never out of order. A scanner keyed on the clause name cannot tell them apart and would
    have filed all three as planning lessons, teaching the planner to fix something that
    was never wrong. The classifier now reads `clauses[].evidence` (`required` vs
    `observed`): prefix → `incomplete_execution`, permutation → `order_clause_violated`,
    anything else → `order_unclassified` rather than being dressed up as a lesson. After
    the correction exactly one genuine reordering remains, and `MIN_OCCURRENCES` correctly
    refuses it.

18. **the regression gate's scope is the whole checkout, not a pinned pair.** It pinned
    **2 verifiers out of 70**, so *"nothing that used to work stopped working"* was a claim
    about 2 checks — an entry breaking any of the other 68 would have been reported
    **KEEP**. Widening it immediately exposed a second defect: the gate ran **every**
    verifier including the chain verifier that contains it, so it re-ran itself and the
    only "new failure" reported was **the verifier containing the gate** — a REVERT caused
    by **recursion**, not by a regression. Both are fixed: `all_verifiers()` is the scope,
    and `SELF_VERIFIERS` is an explicit named exclusion (a glob would quietly grow into
    "skip whatever is inconvenient"). The 18 verifiers that fail are **measured** to fail
    identically on PR base `39016694`; each baseline entry carries `measured_on`, a
    `classification`, why it cannot be attributed to any entry, and what would fix it.
    Result: **52 pass, 18 baselined, 0 new failures, 69 ran**. The gate requires **no new
    failures**, not a green repository — a gate that requires the impossible gets switched
    off, which had already happened here once.

19. **a measured win must be deliverable, not just measured.** `reuse.py` measured the
    spacing lesson fixing **4 instances in T12 and T03**; `retrieve.py` gated on an
    **exact task_family match** and withheld every one of them. Both modules were
    internally consistent and the number was arithmetically right — **it just could not
    reach the caller.** Underneath sat a second defect: `task_family` was a hardcoded
    **default**, so the harness lesson learned from **T05** batches declared itself a
    **T13** spacing lesson — and retrieval acts on that label, making the entry offered to
    the wrong family and invisible to the right one **at once**. Fixed by deriving
    `task_family` from the evidence (batch name, or the run's own template id; **UNKNOWN
    and refused** rather than defaulted), by recording `measured_families` on the activated
    version separately from where it was learned, and by using the union in the retrieval
    gate. Result: **E2 is now offered to T13, T12 and T03, still withheld from T14**, and
    on T12+T03's 18 below-contract plans it fixes **18/18**.

20. **the planner is not "unmeasurable" — it is unmeasurable on ONE thing.**
    `measurable_offline=False` was right about a plan's *quality* needing a model call. It
    is wrong as a statement that nothing about the planner can be checked. The planner's own
    SYSTEM PROMPT says *"If the instruction fixes an order, follow it exactly"* — and
    `validate_plan` only verified that the names were known. **That sentence had never been
    checked.** The archive holds one plan that reversed a required order; it was found only
    **after a full run** — the most expensive way to learn something knowable before the arm
    moves. `check_plan_order` now refuses it, and is **inert** when the instruction fixes no
    order. It is still **not** a correctness judgement: a wrong bin does not trip it.
    A real trap: all 16 same-run plans obeyed the order; the one reversal is a plan authored
    for one task and executed against **another**, so it appears only against the *host*
    instruction. A probe scanning same-run pairs alone reports **0 violations** and the check
    looks untested. `plan_order` therefore reports both numbers.

21. **the third transition exists now.** `lifecycle.py`'s docstring lists three —
    RETIRE, REVISE, KEEP — and only two were implemented. REVISE is the one that covers the
    case that actually occurs: the entry is **not harmful** (so RETIRE is wrong) and **not
    fine** (so KEEP is wrong) because the record is **narrower than what has since been
    measured**. `measured_families` is a snapshot taken at activation; a later measurement
    can outgrow it, leaving the live entry narrower than its own evidence — retrieval then
    withholds the lesson from a family it demonstrably fixes. The measurement is right and
    the record is out of date.
    `revise()` changes **only** `measured_families`: the lesson, its conditions and its
    suggested action are untouched, because a revision that could rewrite the lesson would
    be a second, unreviewed activation wearing a version bump. The previous version stays on
    disk, the chain still verifies, the parent is linked, and it **settles** — a second
    review pass does not revise again.
    Three deliberate calls: **harm outranks staleness** (a wider scope makes harm worse, so
    a harmful entry is retired whatever its scope says); **a consumer the instrument cannot
    see is not "stale"** (that is a blind spot, not an out-of-date record); **REVISED is a
    transition, not an outcome** (counting it as helpful use would credit an entry for a
    bookkeeping change).

`verify.py` asserts **90 checks**, including that both gates really ran, that the asset
binds to a function that exists, that the rejected delivery produced no asset, that
retirement still lets retrieval see nothing, that **no generated record was ever ACCEPTed
without a named reviewer**, that **every entry declares which split its evidence came
from**, that **two distinct consumers act**, that the ACTIVE set spans **both splits**, and
that **an already-conforming plan is a declared invalid condition whose probe reports
INERT**, and that **several candidates were compared with the losers kept and explained**, and that
**the skill fixes at least one task family other than its source while making nothing
worse**, and that **every active entry reached its consumer** while an entry with no
actionable text is reported DROPPED rather than accepted, and that **an order-clause
failure is told apart from a truncated run**, and that **the gate covers every verifier
while not running the one that contains it**, and that **an entry measured to help another
task family is actually offered to it while an unmeasured family is still withheld**, and that **the planner refuses a reversed
order while staying inert when the instruction fixes none**, and that **a record narrower
than its measurement is revised while the lesson text stays untouched**.

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

0. **TWO SPLITS, AND ONLY ONE OF THEM SUPPORTS A GENERALIZATION CLAIM.** Three entries
   are in the store: two spacing entries read `HO-90899d657e68` from
   `benchmark/held_out/unseen_public` (the T12/T13 families exist **only** in the
   held-out set), and one harness/DDS entry reads `evobot_t05_*`, which runs **train**
   seeds s1000–s1005. Every entry carries `evidence.evidence_split` and the verifier
   asserts both splits are represented.

   The harness entry is the first one learned from **development** evidence, and it was
   only found once the scan stopped reading `task*.out` alone: a run whose stack never
   started leaves no task.out, so five archived HARNESS-layer failures — the whole DDS
   participant lesson — were invisible to it. Reading `summary.txt` and then each run's
   `stack.log` (for the cause, not the label "stack unavailable") is what opened the
   development split at all.

   The generator refuses held-out evidence by default under two independent rules: the
   batch's `evidence_index` rung says "Generalization Tested", and the run cites an
   instance in the current sealed set.

   **Still not shown: cross-split transfer.** Nothing here learns on development and is
   measured on held-out.
1. The review artifact is written by a **separate step of the same run**, not by an
   outside reviewer. The schema forbids an AGENT_GENERATED entry from carrying its own
   ACCEPT, but a machine step is still not a person.
2. Every outcome is the effect_spec's expectation met on an **archived** input. No
   Gazebo window and no real robot run were made this round.
3. The **planner consumer's EFFECT is not measurable offline**: a prompt-level delivery
   needs a model call, so it is reported `UNMEASURED`, never scored as no-effect. Its
   **delivery** IS measured deterministically (the text reaches the prompt renderer).
4. The spacing entries are about **one** task family (T13); the harness entry is about the
   T05 relay stack. Nothing in this batch shows transfer to a different task type, and
   **nothing learns on the development split and is measured on held-out** — the two
   active entries are independent, not a transfer result.
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
9. The misuse probes cover the spacing, respread and harness consumers (8 probes). The
   `development` has none, so its entries would report UNPROBED.
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
