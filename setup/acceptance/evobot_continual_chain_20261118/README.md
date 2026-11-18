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

22. **staleness is two-sided, and only one side is safe.** The first version computed
    `added = measured - recorded` and called an empty diff *"not stale"* — so a record
    claiming a task family the instrument **cannot confirm** passed review, and **retrieval
    acts on the claim**, turning an over-claim into an unjustified application. Under-claiming
    costs a **missed reuse**; over-claiming costs a **wrong action**. **Both can be true at
    once** (one family missing, another invented), and an `if/elif` reports only the first
    it checks — so the direction is reported as `both_directions` and the revision fixes
    both. A revision that could only **widen** would leave an over-claim in place forever.

    Also: `apply()` looped over `{"RETIRE"}` only, so a review that returned **REVISE**
    changed nothing — **a loop whose action half ignores half its own findings.**

23. **the ledger must name the TASK.** The master goal's fifth step is *"record how it was
    used afterwards: **which task** retrieved it, what action changed, what the result was."*
    Every ledger row said `run_id="chain-demo"` — **the answer to "which task" was a demo
    label, not a task.** The reason is concrete: the reuse audit is the only place in the
    package that applies a skill to tasks it was **not** built from, and it wrote the result
    into a report file **and nowhere else**. A usage record that omits the usage makes an
    entry with real reuse evidence look identical to one that was **never tried**.
    Now `record=True` writes **three rows per task instance** — `RETRIEVED` (was it offered),
    `APPLIED` (did behaviour change), `OUTCOME` (what happened) — because a single blended
    row would make *"offered but inert"* and *"applied and helped"* look alike. The ledger
    went from **2 applications under one label** to **7 distinct task ids** (`0 → 7` rows
    naming a real task). `record=False` writes nothing, and turning it on does not change a
    single number in the audit.

24. **recording only the wins is the ledger's own documented error, inverted.** Its
    docstring records *"one lesson was retrieved for every task and changed no plan."* Last
    round fixed *which task*; this round found that only the **7 changed** applications were
    recorded, so the ledger reported a **100% hit rate for a 2.4% effect**.

    | | recorded | apparent hit rate |
    | --- | --- | --- |
    | wins only | 7 (all `IMPROVED`) | **100%** |
    | everything | **294** (7 `IMPROVED` + 287 `UNCHANGED`) | **2.4%** |

    Every application is now recorded in one of four kinds: `IMPROVED`, `UNCHANGED`
    (**offered, executed, correctly did nothing**), `WORSE`, and `UNKNOWN` for a skill that
    **refused to run** — a refusal is not scored as an outcome, because counting it as
    "unchanged" would credit it with a result it did not produce.

    Two things had locked the bias in: a test asserted `applied == fixed`, which *is* the
    defect written as an expectation, and the task-id check tested only for `HO-` — which
    **excluded the entire development split** (`T01-train-seed1000`), so a "which task"
    check could pass while half the archive was invisible to it.

25. **a rate must be computed in one unit.** The hit rate reported last round was **2.4%**
    — and wrong, in a specific way: `fixed` was counted **per task instance** while
    `untouched` was counted **per plan file**, and **the same task appears in several
    batches**, so the plan-file denominator is about **2.7×** the instance denominator.

    | basis | denominator | rate |
    | --- | --- | --- |
    | mixed (as reported) | 7 / (7+287) | **2.4%** ✗ |
    | per **instance** | 7 / 109 | **6.4%** ✓ |
    | per **plan file** | 7 / 294 | 2.4% (a *file* rate, not an instance rate) |

    Both counts are useful and they are **not interchangeable** — so the audit now carries
    **both denominators** and the hit rate uses the one that matches its numerator
    (`instance_hit_rate`). Fixing the wins-only bias last round was not enough:
    **the surviving number was itself two units welded together.**

26. **a declared destination is not a covered one.** `consumers.implemented()` checks that a
    consumer's entrypoint **file** exists. That says the address is real; **it does not say
    any mail ever arrived.** The objective names **four** routings; this stack declares all
    four; a check written against the declaration would report **4/4** while only **1** is
    actually carrying an entry.

    | routing | consumer | state |
    | --- | --- | --- |
    | order (操作顺序) | `planner` | **NAMED_BUT_EMPTY** |
    | spread (落点间距) | `spread_policy` | **NAMED_BUT_EMPTY** |
    | recovery (抓放恢复) | `executor_recovery` | **CARRIED** |
    | ROS launch (ROS 启动) | `development` | **NAMED_BUT_EMPTY** — never carried anything |

    Concretely: offering a ROS-launch lesson to `development` returns **UNSUPPORTED** — the
    routing exists and **nothing can arrive**. That is the same *routed-but-undeliverable*
    defect this package fixed twice for other consumers; **it had never been checked for
    this one.**

    `routing_coverage.py` does **not** invent a delivery path to make the number look
    better: a development experience lands in `development_skills/registry.json`, which is
    prose for a coding agent, and there is **no deterministic way** to check that a lesson
    changed an agent's behaviour. Claiming otherwise is the overstatement that registry's
    own README warns about.

    It also reports the ROS-launch lesson **acting from `harness`**, a consumer the
    objective did **not** name — **separately, never counted as coverage of the fourth
    routing.** Counting it would be the rounding-up this module exists to prevent.

27. **no live behaviour change without an entry behind it.** The order rule had been wired
    **straight into `validate_plan`**, so the planner began **refusing plans it used to
    accept** — a real behaviour change with **no entry** behind it. Nothing could review it,
    probe it for misuse, record an outcome for it, or **retire** it, because there was no
    entry to hang any of that on. Step 4 of the objective is explicit that a change is
    validated and versioned **before** it is enabled.

    `order_rule_admitted()` now gates the rule on a **delivered** entry (the `_entry_id`
    marker `delivery.deliver_planner()` stamps), so "arrived" and "acts" are the same
    channel:

    | observation | planner behaviour |
    | --- | --- |
    | no admitted entry | **exactly as before — refuses nothing new** |
    | a delivered entry | refuses a reversed plan |

    The rule stays **directly measurable** (`check_plan_order`), because *measuring a rule
    is not the same as enabling it.* `routing_coverage` now also reports
    `live_rules_with_no_entry` — a rule live in the code path with nothing backing it. That
    is **worse than an empty routing, not better**: an empty routing does nothing, while an
    unbacked live rule changes behaviour and **cannot be retired.**

28. **committed evidence must still describe the code.** verify.py regenerates the chain
    into a **temp** directory and asserts properties of THAT run — a check that the code is
    self-consistent, **not** that the committed artifacts are current. They had **already
    diverged**: after a schema field was added, **18 of 32 files** recorded a chain the
    current code no longer produces, and nothing said so.

    Root cause: `review_ref` was an **absolute path built from the output directory**, and
    it is part of the entry body — so `entry_id` (a digest of that body) **depended on
    where the demo ran**. The same chain written to two places got two identities, which is
    exactly why a committed artifact set could never match a fresh run, and why no freshness
    check could exist until that was fixed. The reference was also dangling: it pointed
    **outside the run directory at a file nothing wrote.**

    `evidence_freshness.py` now compares the committed evidence against a fresh run:

    | class | treatment |
    | --- | --- |
    | **number drift** | **FAIL** — numbers are what a reader quotes |
    | **id churn** | reported as the evidence's AGE, not a failure |
    | missing artifact | FAIL |

    It compares numbers and not bytes: entry ids are digests of the body, so a byte
    comparison would fail on every harmless schema addition and be **switched off within a
    week** — which is how gates stop existing.

    After the fix: committed vs fresh = number drift **0**, id churn **0**, missing **0**,
    with **27 files byte-identical** (baseline count).

29. **the fourth routing now has a delivery path — and it refuses to lie.** The objective
    says ROS-launch lessons belong in development experience. That routing was
    **UNSUPPORTED**: even if an entry had existed, **nothing could arrive**.

    The obvious fix would have been wrong. `development_skills/registry.json` defines
    **PROPOSED** as *"written, unit-tested, mutation-tested"*, and its own `promotion_rule`
    says passing tests is necessary but not sufficient. **An experience entry has no test
    file and no mutation run**, so writing it as PROPOSED would put a **verification into
    the registry that never happened.**

    So delivery renders a **candidate** instead:

    | field | value |
    | --- | --- |
    | status | `CANDIDATE_NOT_IN_REGISTRY` — **not PROPOSED** |
    | effect | **NOT_MEASURED**, as that registry's own legend requires |
    | `missing_for_proposed` | **entrypoints / tests / mutation** — what the entry cannot supply |

    **A candidate that names its own missing tests is more useful than a PROPOSED entry that
    quietly has none.**

    Two inputs are genuinely refused: an entry with **no `applicable_when`** is **DROPPED**
    — *a skill with no stated trigger is never loaded at the right moment*, which is the
    failure mode behind the measured **zero adoption** — and an entry with no actionable text.

    The report also stops blending two different gaps that used to share one label:

    | state | meaning |
    | --- | --- |
    | `CARRIED` | an ACTIVE entry actually arrived |
    | `NO_ENTRY` | **path works, nothing routed here** |
    | `NO_DELIVERY` | **entry exists, cannot arrive** |

    They need different work, so one must not hide behind the other. Now **no named routing
    is NO_DELIVERY**: one CARRIED, three NO_ENTRY.

    One existing assertion pinned "development has no delivery path". It had to fail. **It
    was re-pointed rather than deleted** — at an undeclared consumer, which must still be
    UNSUPPORTED — and a second check asserts the previously unreachable consumer is now
    reachable. Deleting it would have turned *"the gap closed"* into *"the guard went away"*.

30. **`UNROUTED` is a statement about our signature table, not about the world.** The
    generator refuses **7 of 9** signatures as UNROUTED, covering **92 of the archive's 98
    failures**:

    > *"no consumer in this stack declares a change for 'graded_push', so the knowledge
    > would be a number in a document"*

    **That says "nobody wrote a mapping." It reads as "nothing here can act."** The first is
    unwritten work; the second is a measured limit. The objective records the mirror-image
    error: `route_lessons.py` injected a landing-coordinate lesson into a planner that emits
    object→zone, and the plan came out **identical**. **The lesson was true; the address was
    wrong.** UNROUTED is that failure caught one step earlier — or a capable module hiding
    behind a missing table entry.

    Each signature is now measured against a module whose **output** could carry it:

    | state | meaning |
    | --- | --- |
    | `ALREADY_CORRECT` | right on **every** scoreable instance — routing there changes nothing |
    | `FAILED_INSTANCES` | wrong somewhere — **the lesson has a real address and the table is missing it** |
    | `UNMEASURED` | **no probe yet.** Reported as such, not guessed |

    | signature | occurrences | state |
    | --- | --- | --- |
    | `placement_clause_failed` | **14** | **ALREADY_CORRECT** — the planner chose the required bin on **6 of 6** scoreable instances |
    | `graded_push` | 23 | UNMEASURED |
    | `unconfirmed_native` | 31 | UNMEASURED |
    | four others | 24 | UNMEASURED |

    **"Deliver the wrong-bin lesson to the planner" sounds inevitable — and the planner was
    already right.** Delivering it would produce an identical plan, which is exactly the
    `route_lessons.py` trap.

    **The module's own first version failed its own rule:** it asserted *"no capable module"*
    for six signatures **on the strength of their names**. *"Obviously nothing can act on a
    grader verdict"* is still an unmeasured claim, and preventing exactly that is this
    module's purpose. They are now `UNMEASURED` with a hypothesis attached, labelled.

31. **a capable module can exist and the archive still cannot measure it.** Last round split
    UNROUTED into *already correct* and *not yet measured*. **A third answer was missing.**

    `graded_push` — **23 failures across 9 instances, the largest unrouted signature** — is not
    a case with no module. `push_recover` is a real closed-loop retry policy: when a push
    reports contact lost with the object short, it asks for the remainder. Its batch records a
    **with/without comparison**:

    | configuration | terminal pass |
    | --- | --- |
    | single-shot PushObject (baseline) | **2/5** |
    | closed-loop recovery | **4/5** |

    **The capability and the evidence both exist. So why can it not be measured here?**

    > **The recorded attempt sequences were produced BY the policy under test.** Replaying a
    > policy over its own output cannot show what the policy changed — the attempts already
    > contain its decisions. **That is a selection effect, not a null result.**

    All three of the tempting answers are wrong:

    | if reported as | what is wrong |
    | --- | --- |
    | "no capable module" | **one exists** |
    | "already correct" | **not measured** |
    | "still wrong" | **not measured either** — and would hatch a "fix" for an unproven defect |

    It is reported as **UNMEASURED + `module_found: true`**, with the selection effect named in
    the reason. The replay itself **reproduces the recorded verdict in 5 of 5 trials** — a
    **correctness check on the replay, not an effect measurement**, and conflating the two
    would turn this back into "we measured it".

42. **AN "UNROUTED" SIGNATURE WAS ACTUALLY A ROUTABLE PLANNER RULE.** The objective routes
    operation-order lessons to the planner. `graded_visit` was called UNROUTED for lacking an
    executable probe — but inspecting the archive showed a concrete order error:

        instruction: "Move the blue block to the left bin, passing through the RIGHT bin first."
        plan:        [(b, zone_1 LEFT), (b, zone_2 RIGHT)]   <- REVERSED
        why-text:    "Pass through the right bin first as instructed"  <- contradicts the plan

    The planner's order rule only knew "the X block must be put there FIRST", so this clause
    was invisible. Measured against 24 archived instructions:

        first move wrong      21
        true positives        21
        FALSE POSITIVES        0   <- the hard bar
        true negatives         3
        false negatives        0

    **Zero false positives is required:** a rule that refuses a CORRECT plan is worse than one
    that misses a wrong plan, because it changes behaviour on runs that were already right.
    Ground truth comes from each observation's OWN zone positions (right = largest x), never
    from the evaluator's verdict — a check that reads the answer key is not a check.

    The new rule stays gated by `order_rule_admitted`: with no admitted entry the default path
    is byte-for-byte unchanged. It is a capability an entry can authorise, review, and retire —
    not a hard-coded constant.

41. **THE APPLICABILITY GATE CHECKED ONLY 1 OF 4 DECLARED CONDITIONS.** Last round added live
    applicability checking, and the verifier reported "checked". Cross-checking showed the
    gate hard-coded two probe ids, was blind to three of E2's four declared invalid conditions,
    AND misspelled one of them (`spread.single_stage` instead of `respread.single_stage`).

    `_check_applicability` now iterates EVERY declared `invalid_probes` entry:

    - checkable against the real plan → checked, recorded in `checked`
    - unknown probe id → recorded in `unprobed`; **the whole gate refuses**

    An unchecked disclaimer is not a safeguard. Result: `checked=4, unprobed=0` for E2.
    A test pins "declared set == checked set + unprobed set" and that an unknown probe
    refuses rather than silently passes.

40. **A REVIEW CAN BE PRE-GENERATED BEFORE THE ENTRY EXISTS.** `entry_id` is a digest of a
    predictable body. A reviewer can compute the future `entry_id`, write ACCEPT into the
    review ledger BEFORE the entry is stored, then store the entry. The ledger has no
    timestamp and its chain verifies, so the gate could not tell "reviewed after creation"
    from "reviewed before creation".

    Reviews must now also carry `entry_chain_sha256` — the entry's `chain_sha256`, fixed
    only once the entry and its append-only predecessors are actually stored.

    | review | result |
    | --- | --- |
    | entry_id + correct chain anchor | **accepted** |
    | entry_id only (pre-generated) | **refused** |

    **Honest limit:** this assumes the attacker cannot predict the whole entry-chain prefix.
    An attacker who controls the ENTIRE chain can still construct one — that is what a
    signature would solve, and this repo has no signing mechanism. Stated, not hidden.

39. **STEP 5 AT THE LIVE BOUNDARY: AN APPLIED ENTRY IS RECORDED WITH ITS RUN ID.** Until now
    the live path applied an entry's parameters and wrote only `experience_binding.json` — it
    never touched the usage ledger. **"Which task used this entry, what changed, what
    happened" was unanswerable on the only path that runs a robot.**

    The driver now writes three rows when parameters actually take effect:

        RETRIEVED   the entry was looked up for this run
        APPLIED     kwargs were non-empty; the parameters reached apply_respread
        OUTCOME     IMPROVED if the plan changed, else UNCHANGED

    Every row carries the real `run_id`. **An event without a run id cannot be tied to a
    measurement**, which is exactly the "stored but never used" ambiguity this ledger exists
    to remove.

    | case | ledger |
    | --- | --- |
    | independent review + applicable parameters | **three rows written** |
    | no review / defaults used | **nothing written** |
    | plan already conforms, gate refused | **nothing written** |

    **Recording a fallback as APPLIED would recreate the wins-only bias this chain already
    fixed.** End-to-end tests pin all three cases: a real application writes three rows, the
    default path creates no file at all, and an inapplicable plan writes nothing.

38. **THE LIVE GATE NOW CHECKS APPLICABILITY AGAINST THE REAL PLAN.** Objective step 4 requires
    checking that a lesson is not applied in an inapplicable scenario. All earlier misuse
    probes ran on ARCHIVED FIXTURES — a static property of the entry, not of the run. The
    live call site never looked at the entry's own applicability conditions.

    `resolve()` gained an `observation` argument; the driver passes the real `plan.json` via
    `--experience-observation`. Before parameters reach `apply_respread`:

    | real plan | result |
    | --- | --- |
    | two landings already 90 mm apart (contract met) | **refused** — "already meet the spacing contract" |
    | two landings 56 mm apart (below contract) | **parameters accepted** |
    | a single landing | **refused** — "nothing to separate" |

    **A plan that already meets the contract must not be "recovered"** — that would rotate the
    planner's deliberate landings by 64 mm for no benefit.

    Crucially, the probe IDs come from the entry's OWN `invalid_probes` and the threshold from
    its `effect_spec.params` — **not a new standard written into the gate**. Changing the entry
    changes the behaviour; the gate itself stays generic.

37. **THE MOST IMPORTANT GATE HAD A FORGEABLE LEDGER.** Last round made authorisation read an
    independent review ledger keyed by `entry_id`. But that ledger was a PLAIN JSONL file:
    anyone could append a line with a made-up reviewer name and the gate would hand
    parameters to `apply_respread`. **Measured: a forged line was accepted.**

    `review_ledger.py` now gives each review a `review_sha256` / `chain_sha256`, and
    `resolve()` **verifies the chain before consuming any authorisation**:

    | case | result |
    | --- | --- |
    | hand-written forged line, no chain | **refused** |
    | properly chained review | **accepted** |
    | ACCEPT edited to REJECT after the fact | **refused** |

    ### What the chain does NOT prove, stated rather than hidden

    | limit | why |
    | --- | --- |
    | reviewer is who they claim | **needs a signature / external identity** |
    | reviewer cannot append a NEW review | appending is a legitimate operation |
    | tail truncation | a forward-only chain with its last record removed is still a **valid shorter chain** |

    One test originally asserted that deleting the TAIL would be detected. That asserted a
    property a hash chain **does not provide**, so it was changed to detect a **middle
    deletion** and the limits were written into the module docstring and the artifact.

36. **AUTHORISATION MUST COME FROM AN INDEPENDENT LEDGER BOUND TO THE EXACT CLAIM.** The
    previous round's gate read `entry["validation"]["reviewed_by"]` — a field the SAME round
    that authored the entry wrote into the hash chain. **A chain proves a field was not
    tampered with afterwards; it does not prove anybody independent signed off.**

    The repo DOES have a real independent ACCEPT: `gate-auditor`, with a `REVIEW.md`. It is for a
    **CONTROL FACT** built on **exactly E2's three evidence files**. That is a review of a
    **DIFFERENT CLAIM** on the same evidence, and it must not authorise E2's actionable
    spacing recommendation. **Borrowing it would be using a real review to backstop a
    different claim.**

    `resolve()` now reads a SEPARATE review ledger and requires:

        ledger exists -> entry_id EQUALS this entry's identity
                      -> verdict == ACCEPT
                      -> reviewed_by is not chain-demo-reviewer

    Even an ACCEPT on the very same evidence files fails the `entry_id` gate.

    | case | result |
    | --- | --- |
    | no independent ledger | `{}` — defaults |
    | ledger ACCEPTs a different claim | `{}` — defaults |
    | ledger ACCEPTs this entry_id | kwargs reach the call site |

    Two stale assertions (one in `verify.py`, one test) pinned "consumer never reads an
    entry". After the wire landed they were **changed to assert the new behaviour, not
    deleted** — so "the gap closed" did not become "the guard went away".

35. **"CONSUMER NEVER READS AN ENTRY" NOW HAS A REAL WIRE — OPT-IN AND FAIL-CLOSED.**
    `recovery_driver.py` accepts optional `--experience-asset` / `--experience-entries`;
    `live_binding.resolve()` re-checks FOUR gates before any parameter reaches
    `apply_respread`:

        chain intact -> ACTIVE + latest (by store order, not a missing version field)
                      -> INDEPENDENT ACCEPT (chain-demo-reviewer is refused)
                      -> numeric, finite callable kwargs derived from the ENTRY

    Any gate failure returns `{}` and the call site uses its original defaults. No exception
    escapes: a broken experience lookup cannot stop a recovering robot.

    | invariant | why |
    | --- | --- |
    | no flags => frozen baseline byte-identical | the default path keeps apply_respread's signature |
    | kwargs derived from the ENTRY, not the asset's cached callable | an asset is a derivative; editing an artifact must not steer a robot |
    | self-reviewed entry cannot drive the live call | the reviewer must be independent of the run that made the entry |

    Measured now: no flags => `{}`; this chain's self-reviewed entry => `{}` (**refused by
    the independent-review gate**); a copy with an independent reviewer =>
    `{spread_step: 0.09, cluster_m: 0.12}` — **the parameters really reach the call site.**

    **The wire is live; the current entries still cannot drive the robot because they carry
    only a self-review.** That is not a wiring failure — **it is the gate doing its job.**
    Letting an entry through needs a real external review, not a weaker gate.

34. **THE SECOND DIAGNOSIS WAS ALSO WRONG, AND IT IS CORRECTED HERE.** The previous round
    claimed the live path had NO harness/executor consumer. That scan looked only at
    `experiments/baselines/run_*.py` and missed the SHELL runner:

        setup/acceptance/evobot_unified_runner_20261111/run_batch.sh:107
            python3 "$RECOVERY" --run "$D" --ground-truth ...
        runtime/recovery/recovery_driver.py:146
            retried = recover.apply_respread(plan, avoid=avoid)

    **The executor consumer EXISTS.** What is missing is narrower: that call site uses the
    function's DEFAULT kwargs and performs **no experience lookup**. The compiled E2 asset
    carries `spread_step=0.09, cluster_m=0.12` — **identical to the defaults at this
    snapshot**, so behaviour is currently the same. The defect is that a **FUTURE REVISION**
    of the entry (a different spread_step, a narrowed scope) **can never reach the robot**:
    the chain can revise an entry, but the live call keeps using the function signature.

    Three diagnoses, each narrower and more accurate than the last:

    | round | claim | verdict |
    | --- | --- | --- |
    | 1 | schema mismatch; bridge it | **wrong** — entries are non-planner class, refused by design |
    | 2 | no live harness/executor consumer | **wrong** — missed the shell runner; executor consumer exists |
    | 3 | consumer exists but never reads an entry | **accurate** — defaults, no lookup, revisions cannot reach the robot |

    **Narrowing a diagnosis is approaching the truth, not weakening the finding.** A smaller
    correct claim beats a larger wrong one.

33. **THE FIRST DIAGNOSIS WAS TOO COARSE, AND IT IS CORRECTED HERE.** The previous round
    blamed a two-store schema mismatch. Looking at the two ACTIVE entries more closely:

    | entry | failure_class | consumer |
    | --- | --- | --- |
    | `auto-harness_dds_exhaustion` | `tooling` | `harness` |
    | `E2` | `control` | `executor_recovery` |

    The live `retrieve()` admits only `planning`/`state` and its `_NON_PLANNER` word list
    excludes `landing`, `spread`, `participant`. **Both entries are excluded BY DESIGN, not by
    field-name mismatch. A schema bridge would change nothing** — the robot would behave
    exactly as before. Presenting it as a fix was the overstatement this correction removes.

    | consumer | call sites in the live run scripts |
    | --- | --- |
    | `harness` | **0** |
    | `executor_recovery` | **0** |

    `run_baseline_b.py` and `baseline_c.py` never call `apply_respread` and never apply a DDS
    config from an entry; both are hard-coded in the stack. **The chain learned to improve two
    modules the robot never reads.** The only option that changes behaviour is giving the live
    path those consumers, with a reviewed gate before each call.

32. **the loop can be correct and unplugged.** Everything the demo proves is proved INSIDE
    the chain's own harness. The code that hands experience to the planner for a REAL robot
    run (`experiments/baselines/baseline_c.py`) reads a **different store with a different
    schema**:

    | store | reader | fields |
    | --- | --- | --- |
    | `evolution/experience/records.jsonl` | **live path** | `lesson`, `validated`, `provenance_verified`, `record_sha256` |
    | `.../evobot_continual_chain_.../records_v2.jsonl` | **the chain** | `entry_id`, `suggested_action`, `consumer`, `action_kind`, `version`, `validation` |

    **Zero lessons appear in both.** Measured: **2 ACTIVE entries, 0 visible to the live
    path** — one has no `provenance_verified`; one has no independent ACCEPT in the review
    ledger. The order rule also **never fires** on the live path, because `baseline_c` writes
    experience items **without `_entry_id`** and the gate correctly declines them. The gate
    is right; the consequence is that a rule is inert in the only path that runs a robot.

    This is **measured rather than silently wired up**, because closing it means choosing
    which schema wins, and **both choices have a cost**:

    | option | cost |
    | --- | --- |
    | write v2 into the live store | live retrieval needs `provenance_verified`, `evidence_files` and a review ledger keyed by `record_sha256`; **v2 has none**, so the filter would admit nothing — **fail-closed doing its job** |
    | teach the live path v2 | it would need v2's review verdict and lineage status, and **the file it reads is the one a frozen baseline experiment uses** |

    **Not a one-line change; choosing one quietly is exactly the decision that should be
    visible.** The artifact reports the numbers and both options, and **does not pretend the
    loop is closed.**

`verify.py` asserts **154 checks**, including that both gates really ran, that the asset
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
than its measurement is revised while the lesson text stays untouched**, and that
**an over-claiming record is caught in the other direction too**, and that **the ledger names
the real tasks a skill was used on, each with its own three events**, and that **inert
applications are recorded so the hit rate is not 100% by construction**, and that **the reported rate is computed in
one unit rather than across two**, and that **the objective's four routings are reported
one by one with a declared-but-empty destination not counted as covered**, that **no rule is
live in a code path without an entry admitted for it**, that **the committed evidence
ids, numbers and file set match a fresh run to the byte**, that **the development
routing renders a candidate that does not claim PROPOSED and names its own missing tests**,
that **every unrouted signature states what is actually known rather than being dismissed
with one sentence**, and that **a capable module with an unmeasurable archive is reported as
a selection effect rather than as any of the three tempting answers**, and that **the
chain's connection to the live planning path is measured and reported as unplugged, with the
cost of both ways to close it**, that **a schema bridge cannot rescue these entries**, and
that **the executor consumer exists in the shell runner**, that **the new opt-in wire leaves the no-flag path at its defaults**, that **a self-reviewed entry cannot drive the live call**, that **an ACCEPT for a different claim on the same evidence cannot drive it either**, that **the review ledger is chained and its integrity limits are stated honestly**, that **applicability is checked on the real run plan, refusing a lesson where its own declared invalid condition fires**, that **a live application writes RETRIEVED/APPLIED/OUTCOME with a run id while a fallback writes nothing**, that **a review is anchored to the entry's chain hash so it cannot be pre-generated before the entry exists**, that **every declared invalid condition is accounted for — unknown probes refuse rather than silently pass**, and that **a previously-unroutable order signature is now a measured, zero-false-positive planner rule still gated by an admitted entry**.

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
