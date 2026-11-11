# The independent review found my two verified records teach FALSE lessons

**Date** 2026-11-12 · **Verdict: 0 of 6 records are review-grade. Both new records REJECTED.**

---

## 1. What the review found

| record | provenance | lesson | failure_class | verdict |
| --- | --- | --- | --- | --- |
| `T05-recover-occupied-stage` (ec 61) | **YES** | **NO** | **NO** | **REJECT** |
| `T05-recover-declared-occupied` (ec 60) | **YES** | **NO** | **NO** | **REJECT** |

**Provenance is genuinely fixed** — the reviewer opened the files rather than trusting my checker, and both
evidence strings are in harness-produced `.json`/`.out` artifacts with no prose leaking through the `.md`
exclusion. `evidence_files[]` is truthful in both.

**But the lessons are wrong.**

### R5: the plan was correct

```
a-0 planned [0.092,-0.150],  b-1 planned [0.148,-0.150]  ->  56.0 mm apart
clearance_m 50.0 mm                                       ->  +6.0 mm margin
box a actually landed [0.099744,-0.155761]                ->   9.65 mm error
position_tolerance_m accepts 20.0 mm                      ->  the error was ACCEPTABLE
actual separation 48.6 mm -> 1.4 mm below clearance -> 'destination occupied'
```

The plan did exactly what my lesson prescribes. Then a **9.65 mm error inside the accepted 20 mm tolerance**
ate the 6 mm margin. `position_tolerance_m` is **3.3× the margin**, so an *acceptable* error is **guaranteed**
to break the next stage. My lesson's premise is false, the planner cannot run the check it asks for (it plans
before anything moves), and reordering cannot help when both objects go to the same bin.

### R6: the lesson misdescribes its own artifact

`plan_retry.json` has **one** stage. My lesson opens *"a plan whose **second move** names an already taken
destination"* — there is no second move. And the planner never named a taken destination: it named a spot that
was free until box a landed 9.65 mm off.

**Neither is a planning failure.** The plan was correct in both cases. R5 is control or tooling; R6 is
tooling or state.

## 2. Why this is worse than the four legacy records

> A record that fails provenance gets **rejected**. A record that **passes provenance and teaches the wrong
> lesson gets retrieved and acted on.**

That is the reviewer's sharpest sentence and it is correct. I had built the check that keeps out unverifiable
evidence, and then put two confidently-worded false lessons through it.

## 3. The reviewer also found my verifier was not stronger — it was weaker

Four defects, all real, two demonstrated by admitting a fabricated record:

| # | defect | consequence |
| --- | --- | --- |
| 1 | `if r.get('provenance_verified') is True:` made provenance **opt-in** | a record omitting the field got **zero** checking — including all four legacy records. The reviewer appended *"the gripper spontaneously recited poetry and the task was abandoned"* with no such field and **the gate passed** |
| 2 | `is True` is a type check | the string `'true'` also passed |
| 3 | `SEVEN` had **six** entries — `store_version` missing | the comment and commit both claimed seven. **A name that overstates a check is the same defect class as `validated: true` set by the seeder** |
| 4 | `all(validated)` removed with no replacement | a record with `validated: false` and no provenance claim passed where the OLD verifier failed it |

I had written *"the replacement is strictly stronger"* and shipped it. It was not, and I judged my own case.

## 4. What I changed in response

**`verify.py` now derives provenance instead of trusting the record's claim.** For every record, every time:

```
provenance_derived_ok : 2
provenance_failed     : 4
provenance_failed_ids : [T01-train-seed1000, T05-train-seed1000,
                         T05-train-seed1004, T03-heldout-seed9000]
retrieved_lessons     : 0
```

- Provenance is **mandatory and derived**; a record cannot assert its way past the gate, and `SEVEN_FIELDS`
  now has seven entries with `assert len(...) == 7`.
- The four legacy failures are **published in the output**, not skipped — a verifier that quietly skipped
  them is how this defect survived four rounds.
- The assertion that retrieval must be **non-empty is gone**. It assumed the store holds something
  trustworthy; both verified records were rejected, so **zero is the correct answer**, and forcing
  non-emptiness would push a wrong lesson into a plan. It now asserts the property that can actually fail:
  **no REJECTED lesson reaches retrieval.**

**A review ledger** (`evolution/experience/review_ledger.jsonl`) records the independent verdict per
`record_sha256`, and `retrieve()` excludes REJECTed records. Retrieval now returns **0 lessons for every
template**, including T12/T13/T14 — the honest state.

## 5. What is true now

| claim | status |
| --- | --- |
| provenance check works and catches prose-only evidence | **YES** |
| provenance check verifies **numbers** | **NO** — `evidence_strings()` skips values under 8 chars, so `error_code 99` passes. The reviewer demonstrated it. **Open.** |
| lessons are checked against the evidence's numbers | **NO** — this is what would have caught R5/R6. **Open.** |
| an independent REJECT stops a lesson reaching a plan | **YES, via the ledger** |
| the store holds a review-grade record | **NO — 0 of 6** |
| the verifier is stronger than what it replaced | **YES now**; it was not when I claimed it |

## 6. The reviewer corrected themselves, and it matters

On R3, the round-12 disagreement: the reviewer had trusted R3's evidence because their grep truncated paths
and **three directories are named `s1004-a1`**. They attributed `evobot_t05_batch`'s (domain 213) to
`evobot_t05_n6`'s (domain 233). **My checker was right and their reason was wrong** — recorded in their own
words. R3's rejection stands on provenance as well as scope and class.

## 7. What I am not doing

- **Not deleting the two rejected records.** The store is append-only and the mission forbids deleting
  failure evidence; they now carry an independent REJECT in the ledger and are excluded from retrieval.
- **Not rewriting their lessons** into something defensible. The reviewer's fix 5 says the real lesson is
  *"with a ±28 mm spread, a 9.65 mm placement error leaves 1.4 mm against a 50 mm clearance"* — a
  control/tooling finding. Writing that as a new record is a next-round job with its own provenance, not a
  patch to these.
- **Not claiming P4 progress.** Retrieval reaching the unseen templates was a precondition; the records that
  reached them were false. **P4 remains `EVOLUTION_ADVANTAGE_NOT_DEMONSTRATED`.**