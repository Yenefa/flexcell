# The experience channel: one plan-changing lesson, zero machine-verifiable records

**Date** 2026-11-12 · **Subject** `evolution/experience/records.jsonl` (4 records, hash chain intact)
**Status: P3 experience records audited. An independent review is commissioned separately and is NOT yet in.**

---

## 1. Why this audit, and what P3 actually requires

P3 requires **seven-field experience records with independent review**. `store.py` already produces
seven-field records (task_id, failure_class, evidence, lesson, source_run, outcome, validated, plus the
hash-chain fields), and its docstring is explicit about the design intent:

> *"experience records are MACHINE-GENERATED from verifier evidence, not written by the model as prose…
> evidence = measured facts, never a self-claim."*

**That is the claim this audit tests.** Not whether the records exist — they do, and the chain verifies —
but whether they are what they say they are, and whether they can do anything.

## 2. Can any lesson change a plan? One of four.

Re-running `evolution/transfer/audit_actionability.py` over the validated records:

| task_id | class | actionability |
| --- | --- | --- |
| T01-train-seed1000 | planning | **PLANNER_ACTIONABLE** |
| T05-train-seed1000 | runtime | HARNESS |
| T05-train-seed1004 | runtime | HARNESS |
| T03-heldout-seed9000 | planning | DOWNSTREAM_CODE |

```
validated lessons: 4    ACTIONABLE FRACTION: 1/4
At most 1 of 4 lessons could ever move a plan.
```

Two are harness concerns outside the planner; one describes a landing-spot detail the planner never emits
(it emits zone names only, and the spread is computed afterwards). **Three of four are true and inert.**

## 3. The one actionable lesson addresses a failure that never occurs

That lesson is *"Declare exactly the objects present in the world…"*, sourced from `error_code = 64`
(`ERR_INVALID_PLAN`, 2 observed vs 3 declared objects).

Searching every machine-readable archive file for `"error_code": 64`:

```
NONE.

The detail string 'must declare every observed object' appears in the acceptance archive exactly 3 times,
and every one of them is a README.md. No log, no episode, no JSONL carries it.
```

So the only plan-changing lesson in the store describes a failure mode that **does not appear anywhere in
the machine-readable record of what this project has actually run**.

## 4. And no record's evidence is machine-verifiable

Checking each record's `evidence` strings against its own cited `source_run`, across all file types:

| record | cited `source_run` | files containing the cited evidence | machine-readable |
| --- | --- | --- | --- |
| T01-train-seed1000 | `evobot_t01_baseline_a_20261111` | 1 | **0 — README.md only** |
| T05-train-seed1000 | `evobot_t05_batch_20261111` | 1 | **0 — README.md only** |
| T05-train-seed1004 | `evobot_t05_n6_20261111` | 1 | **0 — README.md only** |
| T03-heldout-seed9000 | `evobot_heldout_n6_20261111` | 1 | **0 — README.md only** |

**0 of 4 for the exact cited strings.** Every record's evidence, as written, is prose that someone composed about a run. That is a claim
about a measurement, not a measurement a reader can re-derive — exactly what the store's docstring says the
records are not.

I am not calling them fabricated. The runs happened; the READMEs narrate them. The finding is narrower and
still material: **the provenance chain from record to machine-readable measurement is broken for all four.**

## 5. What this makes P4 answerable with, and it is a mechanism not an absence

P4 asks whether cross-task experience reuse produces measurable gain over B and C on frozen unseen tasks,
and requires `EVOLUTION_ADVANTAGE_NOT_DEMONSTRATED` if it does not.

| layer | finding |
| --- | --- |
| retrieval | 1 of 4 lessons could act on a plan |
| that lesson | addresses an error code absent from every machine-readable archive file |
| evidence | 0 of 4 records re-derivable from its own cited source |
| therefore | **a D arm reusing this store has at most one lesson, about a failure never observed, on unverifiable evidence** |

So the honest P4 statement is stronger than "we did not measure it":

> **EVOLUTION_ADVANTAGE_NOT_DEMONSTRATED — and the mechanism is that the experience channel contains no
> lesson that can act on any task this project has run, so an experience-reuse arm has nothing to reuse.**

**I am not declaring P4 complete.** D's definition is still unformalised (`§7.5` says it must not remain
undefined, while also saying the definition is only a proposal pending the North Star, and North Star
§8–§14 is `BLOCKED_MISSION_TEXT_MISSING`). What this establishes is a **precondition failure** that any
future D would inherit.

## 6. The independent review, and where it corrected me

`gate-auditor` reviewed all four records against their cited sources. Its verdict:

```
0 ACCEPT / 1 ACCEPT-WITH-CORRECTION / 3 REJECT
```

**It found a cause I missed, and it is better than mine.** My audit stopped at "the evidence is only in
prose". The review found *why*:

> The archive holds the **post-fix** run while the evidence describes the **pre-fix** failure. The defect was
> fixed before the directory was archived, so the cited source cannot contain it by construction. A reader
> doing exactly what `source_run` invites — open it and check — finds a **passing** run in 3 of 4 cases.

I verified its two sharpest claims myself:

| claim | my check |
| --- | --- |
| R1's cited run **passed**, contradicting the record's `outcome: failed` | **CONFIRMED.** `evobot_t01_baseline_a_20261111/task.out` = `{"ok": true, "outcome": 0, "error_code": 0, …}` |
| R4's `task_id` appears in no artifact of its cited source | **CONFIRMED.** `T03-heldout-seed9000` occurs **0 times** in `evobot_heldout_n6_20261111` |

The review also established, and I had not checked:

- **`validated: true` records "the seeder ran", not "a second party checked".** `store.make_record` sets `False`
  (`store.py:56`), then `seed_from_evidence.py:31` overwrites it to `True` before append. Nothing else writes
  it. The field name promises a review that never happened.
- **The scope guard does not guard what it claims.** All 8 lessons/evidence blocks pass `_check_scope`, yet 3 of
  4 lessons are not planner-level. It is a keyword denylist against smuggling *the answer*; it has no test for
  the property `store.py` promises. R4 passes it while describing the correct strategy for same-bin targets,
  because it says "landing spots" rather than "placement". **A denylist evadable by one synonym is not a
  boundary.**

### 6.1 Where I did not confirm the review, and I am recording the disagreement

The review states R3's evidence *"is REAL (the only record whose evidence is in actual run logs)"*. **That is
not confirmed for the cited string.** The exact text — *"Failed to find a free participant index for domain
213"* — appears **only** in that batch's `README.md:19`.

What *is* in the run logs is the same **class** of failure with **different numbers**:

```
runs/s1004-a1/stack.log:19   Failed to create unicast sockets for domain 233 participant index 0:
                             resulting port numbers (65660, 65661) are out of range
```

**domain 233, not 213**, and different wording. So the review's broader point has a basis — DDS participant
exhaustion genuinely occurred and was logged — while its specific claim that R3 escapes the provenance defect
does not hold on the record as written.

I am recording both readings rather than silently adopting the more flattering one. On the exact strings my
figure stands: **0 of 4**. On the underlying events, R3 is the one record where the failure genuinely appears
in a log, with the record's numbers not matching the log's.

## 6.2 The review's ranked fixes, which I accept and will not apply unilaterally

1. **Make the seeder verify provenance mechanically** — assert the evidence values appear in a file under
   `source_run`. About ten lines, and it would have rejected 3 of 4. *This is the difference between a claim
   and a check.*
2. Point `source_run` at the **run** (`runs/s1000-a1`), not the batch directory.
3. **Archive the failing run when fixing a defect** — all three misattributions come from fixing a bug and
   archiving only the success.
4. Replace `validated: true` with explicit reviewer fields written by the reviewer.
5. Wire `audit_actionability` into the **write** path so non-planner lessons are refused on entry.

**None applied.** They change the experience pipeline, and items 4–5 change the record schema. Recording them
as agreed work rather than doing them inside an audit.

## 7. What I did not do

- **Did not modify `records.jsonl`, `store.py`, or any evolution file.**
- **Did not add records.** Adding new ones while the provenance defect is open would deepen it.
- **Did not reclassify any lesson** to raise the actionable fraction. A classifier that is given four inputs
  and reports one actionable is honest; one tuned until it reports four is the same substitution of a label
  for a cause this project has recorded six times.

## 8. Reproduce

```bash
python3 evolution/transfer/audit_actionability.py                 # 1/4 actionable
python3 setup/acceptance/evobot_lead_experience_review_20261112/audit_records.py
```

The second script re-runs all four questions — chain, actionability, machine-readability of each cited
evidence string, and whether the actionable lesson's error code appears anywhere machine-readable.