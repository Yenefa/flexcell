# Independent review of the four experience records

**Reviewer** gate-auditor · **Date** 2026-11-12 · **Subject** `evolution/experience/records.jsonl`
(4 records, store_version 0.1.0) · **Constraint** nothing under `evolution/` was modified.

Chain integrity was re-verified independently: `verify_chain` → **True, 'chain intact (4 records)'**.
All four records are hash-valid and internally consistent. **That is not the same as being true,**
and the distinction is the substance of this review.

---

## 1. Verdict table

| # | task_id | verdict | reason |
| --- | --- | --- | --- |
| R1 | T01-train-seed1000 | **ACCEPT-WITH-CORRECTION** | Lesson is planner-actionable and supported by the source, but `outcome: failed` is contradicted by the cited run, which **passed**, and `error_code 64` exists in **no artifact** — it predates the archive. |
| R2 | T05-train-seed1000 | **REJECT** | `err 41` appears in **no artifact** of the cited source (README prose only); the named task's run **passed** (`outcome=0`). Lesson is an **executor code change**, not planner-level. |
| R3 | T05-train-seed1004 | **REJECT** | Evidence is genuine and is the only record whose evidence is in real run logs — but the lesson is **harness configuration** (ROS domain id), outside the planner entirely, and `failure_class: runtime` is the **wrong class** (`tooling`). |
| R4 | T03-heldout-seed9000 | **REJECT** | `task_id` appears in **no artifact** of the cited source; the T03 run there failed with `err 62`, not `err 60`; `err 60` exists only as README prose about an **unarchived earlier round**. Lesson is **downstream code**, which cannot change a plan. |

**0 ACCEPT · 1 ACCEPT-WITH-CORRECTION · 3 REJECT.**

---

## 2. The systematic defect, not four separate mistakes

Three of four records share one cause, which is why this is a design finding rather than typos.

`seed_from_evidence.py` docstring claims:

> *"Every record points at an archived run directory that still exists. The evidence is copied
> from what the run actually logged. Nothing here is a recollection."*

**That is false for 3 of the 4 records.** The code never checks it: the only test applied to
a source is `source.exists()` (`seed_from_evidence.py:26`). Nothing opens the run and looks
for the evidence.

What actually happened:

| record | cited source contains | where the cited error actually is |
| --- | --- | --- |
| R1 | 1 run, **PASS** (`outcome=0, error_code=0`) | `README.md:40`, a defect fixed *during setup* |
| R2 | 6 runs, `s1000-a1` **PASS** | `README.md:34,55`, a defect fixed *before these runs* |
| R3 | `s1004-a1` **never started** (harness error) | **real artifact**: `s1004-a1/task.out`, `stack.log` |
| R4 | 6 runs, **all PASS** | `README.md:45`, an *earlier unarchived round* |

The pattern: **the archive holds the post-fix run, and the evidence describes the pre-fix failure.**
The failure was fixed *before* the directory was archived, so the cited source cannot contain it by
construction. Only R3 escapes this, because the domain-exhaustion failure was never fixed and its
failed runs were archived as-is.

This matters because the record's purpose is auditability. A reader who does exactly what the
`source_run` field invites — open it and check — finds a **passing** run in three cases out of four.

---

## 3. Per-record detail

### R1 — T01-train-seed1000 · planning · `error_code 64`

- Cited source `setup/acceptance/evobot_t01_baseline_a_20261111` contains one run whose
  `task.out` reads `{"outcome": 0, "error_code": 0, "completed_stage_ids": [...]}` —
  a **success**. The README headline is `独立验收 PASS`.
- `error_code=64` occurs in the source **once**, as a README section heading under
  *"途中修掉的两个真实缺陷"* (two real defects fixed along the way).
- The evidence values `declared_objects: 3` / `observed_objects: 2` are a faithful reading of
  README:41–42 ("the generator assumed 3 blocks a/b/c, but the default world only has a and b").
  They are **prose-derived, not measured fields**.
- The lesson — *"An asset that exists elsewhere is not an object in this scene"* — is genuinely
  planner-level and is exactly what the README concludes (*"I treated 'the asset exists' as
  'it exists in the scene'"*). The repo's own `audit_actionability.py` classifies it
  **PLANNER_ACTIONABLE**, the only one of the four.

**Correction required:** `outcome: "failed"` must not stand against a run that passed.
Re-label as a pre-run generator defect (outcome `not_applicable`/`defect_fixed`), or repoint
`source_run` at the run that actually produced `error_code 64`. The lesson itself may stay.

### R2 — T05-train-seed1000 · runtime · `error_code 41`

- `grep "err 41"` over the cited source returns **two hits, both in README prose** (lines 34, 55).
  `grep "error_code.*41"` over run artifacts returns **zero**.
- The named task's run `s1000-a1` has `outcome=0`, `verdict.passed: true`.
- README:29–47 documents this as a **real and well-diagnosed bug** — `RunComposite` dispatches the
  next stage before the previous goal handle releases, and `acquire(blocking=False)` rejects a
  legitimate plan. The fix was `acquire(timeout=5.0)`.
- The lesson text matches the README almost verbatim. **The lesson is true.**
- But it is **not planner-level**: *"allow a bounded admission wait"* is a change to executor
  code. A planner cannot express it; there is no plan field for an admission wait. The repo's
  own audit classifies it **HARNESS — 'outside the planner entirely'**.

**Reject on two independent grounds:** outcome contradicts the cited run, and the lesson breaches
the store's stated purpose (*"a record may describe a PLANNER-level lesson only"*).

### R3 — T05-train-seed1004 · runtime · participant index exhaustion

- **Evidence is real.** `s1004-a1/task.out:1` and `stack.log:50,137,193` all carry
  `Failed to find a free participant index for domain 213`. The run never produced a verdict
  because the stack never came up. This is the **only** record of the four whose evidence is
  in actual run logs rather than narrative.
- **Wrong class.** `runtime` means the robot's runtime. This is ROS/DDS infrastructure — the
  source README says so explicitly (*"Gazebo stack did not come up, **nothing to do with the
  agent**"*, t05_batch README:23). The correct class from the 11 allowed is **`tooling`**.
- **Not planner-level.** *"Give each stacked run a valid distinct domain id"* is test-harness
  configuration (`ROS_DOMAIN_ID`). A planner has no domain id. Repo audit: **HARNESS**.
- Note the irony: the lesson's own clause *"...and looks like a motion failure"* is the
  interesting part, and it is an **evaluator/attribution** lesson — which the scope guard's
  own `FORBIDDEN_TOPICS` would have blocked had it been phrased plainly.

### R4 — T03-heldout-seed9000 · planning · `error_code 60`

- **The task_id does not exist in the source.** `T03-heldout-seed9000` appears in exactly two
  places in the repo: `seed_evidence.json` and `records.jsonl` — i.e. only in the store itself.
  The six runs in the cited directory are `HO-*` ids; the T03 one is **`HO-13c5efca228e`**
  (`template_id: T03_ordered`).
- That T03 run failed with **`error_code 62`**, not 60:
  `{"outcome": 1, "error_code": 62, "detail": "native terminal/verification unconfirmed
  for target_box_a-1"}` — and its **verdict passed** (`passed: true`), which the README calls the
  round's one *disputed* case.
- `error_code=60` appears in the cited source **nowhere** except README:45, under
  *"修掉的模板设计缺陷"* — describing the **first round** of held-out, which is not archived here.
- All six archived runs in that directory passed independent acceptance (6/6).
- **Lesson is downstream code.** *"distinct landing spots, not the same centre point"* is the
  `spread_destinations.py` fix. Per `audit_actionability.py`: *"the planner emits zone names only;
  landing coordinates are computed afterwards by spread_destinations — so a lesson about landing
  spots cannot change a plan no matter how true it is"*. Repo audit: **DOWNSTREAM_CODE**.

---

## 4. The scope guard does not guard what it claims

`store.py` says *"a record may describe a PLANNER-level lesson only"*. `_check_scope` enforces
this by substring-blocking 17 `FORBIDDEN_TOPICS`.

I ran `_check_scope` over every lesson and every evidence dict: **8/8 PASS**. No record trips the
guard.

Yet by the repo's own actionability audit, **3 of 4 lessons are not planner-level**
(`HARNESS` ×2, `DOWNSTREAM_CODE` ×1). So:

**The guard blocks answer/grading leakage — and it does that job — but it has no test at all for
the property the docstring promises.** It is a keyword denylist against *smuggling the answer*,
not a scope check against *lessons a planner cannot act on*. R2 and R3 pass the guard while
describing executor and test-harness behaviour respectively, because no forbidden word appears in
either.

Meanwhile R4's lesson is the closest thing to a leak — it describes the correct placement strategy
for same-bin targets — and it passes because it says *"landing spots"* rather than *"placement"*.
That is fine on the letter of the rule and worth noting on its spirit: a denylist that can be
evaded by one synonym is not a boundary.

---

## 5. `validated: true` records a seeding event, not a review

Confirmed. `store.make_record` sets `validated: False` (`store.py:56`); `seed_from_evidence.py:31`
then **overwrites it to `True`** before appending. Nothing else in the repo writes that field.

So `validated: true` means *"the seeder ran"*. It is presented in a field name that every reader
will interpret as *"a second party checked this"*. **All four records carry it, and three of them
are misattributed.** This review is the first independent verdict recorded against them;
`REVIEW.md` is deliberately outside `evolution/` so the store stays append-only and untouched.

---

## 6. Overall verdict

**These four records are not evidence that the experience channel works. They are evidence that
it can be populated, and that its integrity machinery runs.**

- The **hash chain is genuine** — I re-verified it. It proves the bytes were not edited after
  writing. It cannot prove the bytes were true when written, and three of four were not.
- The **evidence pipeline is not what the docstring says**: records are seeded from a
  hand-written `seed_evidence.json`; the seeder checks only that a directory exists; no code
  ever confirms the evidence appears in the cited source.
- **Evidence quality is inverted relative to apparent rigour**: the one record whose evidence is
  real run output (R3) is the one that should be rejected on scope and class, while the one
  record with a sound planner lesson (R1) carries a false `outcome`.
- **1 of 4 lessons is planner-actionable**, and it is the one with the false outcome field.

For P3's seven-field requirement, the honest statement is: the *format* is satisfied and the
*chain* is intact, but **independent review finds 0 of 4 records acceptable as written**. The
channel's mechanism deserves credit — hash chain, append-only, scope guard exist and work — but
the contents do not yet meet the standard the mechanism was built for.

---

## 7. What would fix it, ranked

1. **Make the seeder verify provenance mechanically.** For each record, assert the evidence
   values appear in a file under `source_run`. This alone would have rejected 3 of 4. It is a
   ~10-line change and it is the difference between a claim and a check.
2. **Point `source_run` at the run, not the directory.** `setup/.../runs/s1000-a1`, not
   `setup/.../evobot_t05_batch_20261111`. A directory of six runs cannot pin one failure.
3. **Archive the failing run when you fix a defect.** All three misattributions come from
   fixing a bug and archiving only the success. Keep the pre-fix run.
4. **Replace `validated: true` with an explicit reviewer field** (`reviewed_by`, `review_verdict`,
   `review_ref`) written by the reviewer, and leave the seeder emitting `validated: false`.
5. **Add an actionability check to the scope guard**, reusing `audit_actionability.py`, so a
   HARNESS or DOWNSTREAM_CODE lesson is refused at write time rather than found at audit time.

Items 1–4 are cheap. Item 1 is the one that turns this from a self-report into a record.
