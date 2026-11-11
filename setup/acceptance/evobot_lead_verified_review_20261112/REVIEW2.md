# Independent review — the two round-14 records, and the verifier change that admitted them

**Reviewer** gate-auditor · **Date** 2026-11-12 · **Subject** records 5–6 of
`evolution/experience/records.jsonl`; `verify_provenance.py`; `baseline_c_skeleton/verify.py`.
**Nothing under `evolution/` was modified.** No sim, no model calls.

---

## 0. Bottom line

**Neither record is review-grade. Provision is genuinely fixed; diagnosis is not.**

| # | task_id | provenance | lesson supported | class right | verdict |
| --- | --- | --- | --- | --- | --- |
| R5 | T05-recover-occupied-stage (ec 61) | **YES** | **NO** | **NO** | **REJECT** |
| R6 | T05-recover-declared-occupied (ec 60) | **YES** | **NO** | **NO** | **REJECT** |

Both records prove the provenance checker works — it verified the narrative string in a real
run artifact, and I reproduced that independently. Both then misdiagnose the failure they
correctly cite, and both carry the wrong `failure_class`.

Separately: **`baseline_c_skeleton/verify.py` is not strictly stronger than what it replaced.**
I found three defects and demonstrated two of them by admitting a fabricated record.

---

## 1. Provenance — CONFIRMED, checked by hand

I did not trust the checker; I opened the cited files.

**R5** cites `.../HO-90899d657e68/failure_evidence.json`, which reads:
```json
{ "outcome": 1, "error_code": 61,
  "detail": "state drift or occupied destination before target_box_b-1",
  "completed_stage_ids": ["target_box_a-0"] }
```
Exact string, exact code. Also in `task.out`. Genuine artifact of the run.

**R6** cites `.../task_retry.out`, which carries
`"error_code": 60 ... "detail": "unhandled exception: CompositeError: declared destination
occupied at target_box_b-1 ..."`. Exact string, exact code. Also in
`sim/skills/composites/composite-34f3ca6017de4390.jsonl`. Genuine.

I also checked the two things you asked about:
- **The `.md` exclusion did not let prose through.** Both hits are `.json` / `.out` files
  produced by the harness, not summaries.
- **`evidence_files[]` is truthful** in both records — the named file is the file that holds the string.

**Provenance is the strongest part of this round and it is real.**

### But the checker verifies no number, and I can prove it

`verify_provenance.evidence_strings()` keeps only strings ≥ 8 chars; **all numbers are skipped**.
I fed it deliberately corrupted versions of R5's evidence:

| evidence submitted | checker verdict |
| --- | --- |
| `{"detail": <real>, "error_code": 99}` | **passes** |
| `{"detail": <real>, "error_code": 0}` | **passes** |
| `{"detail": <real>, "outcome": 0}` | **passes** |
| `{"detail": "the robot tripped over a cable..."}` (fabricated) | **rejected** ✓ |

So the two fields that decide what these records *mean* — **ec 61 vs ec 60** — are unverified.
They happen to be correct, because the author was honest. The check does not establish it.
For these two records that distinction is load-bearing: 61 and 60 are the *only* thing
separating them, and swapping them would produce two plausible, provenance-passing, wrong records.

---

## 2. R5 — the lesson is not supported by the evidence. The plan was correct.

This is the one you flagged, and the evidence does license a rejection.

### What actually happened, from the artifacts

| quantity | value |
| --- | --- |
| stage a-0 planned destination | `[0.092, -0.150]` (zone_1 centre `0.120`, spread `-0.028`) |
| stage b-1 planned destination | `[0.148, -0.150]` (spread `+0.028`) |
| **planned separation** | **56.0 mm** |
| `clearance_m` | 50.0 mm |
| **planned margin over clearance** | **+6.0 mm** |
| where box a actually landed | `[0.099744, -0.155761]` |
| **placement error** | **9.65 mm** |
| `position_tolerance_m` (accepted error) | **20.0 mm** |
| **actual separation to b-1's destination** | **48.6 mm — 1.4 mm BELOW clearance** |

**The plan did exactly what the lesson tells it to do.** It put both objects in the one bin the
task requires, and it de-overlapped them 56 mm apart — 6 mm outside the clearance. Then box a
landed **9.65 mm** off, which is **inside** the 20 mm placement tolerance the system accepts, and
that error alone consumed the 6 mm margin and 3.65 mm more.

> An error well within accepted placement tolerance is guaranteed to break the next stage, because
> `position_tolerance_m` (20 mm) is **3.3×** the spread margin (6 mm) the plan has to work with.

### Why the lesson fails its own evidence

1. **Its premise is false here.** *"Before sending a second object into an area, check that area is
   still free"* — the plan did allocate two distinct, free, clearance-satisfying spots. The area
   *was* free when the plan was made. It stopped being free because of execution error.
2. **The planner cannot run the check the lesson asks for.** The planner emits
   `{object, zone, why}` at plan time, before anything moves. It cannot observe where the first
   object ends up. *"Check the area is still free"* at plan time is checking the planned world,
   which the plan already satisfied.
3. **Its remedy is unavailable and would not help.** *"order the moves so a later stage is not
   blocked by an earlier one"* — the task puts **both** objects in the **same** bin, so the
   conflict is symmetric. Reversing the order relocates the 6 mm margin onto the other stage and
   changes nothing.

The lesson generalises from *"a 9.7 mm placement error ate a 6 mm margin"* to *"plan the order
better"*. That is a different failure than the one measured.

### `failure_class: planning` is wrong

The plan was correct; the agent's planning was not the defect. The defect is the interaction of
placement accuracy with a clearance margin smaller than both the accuracy and the tolerance.

- **`control`** is the class I would apply — the proximate cause is a 9.65 mm placement error
  against a 6 mm margin, and the tolerance that permitted it.
- **`tooling`** is defensible if you attribute it to the parameter set (`spread_destinations`
  ±28 mm vs `clearance_m` 50 mm vs `position_tolerance_m` 20 mm) being mutually inconsistent.
- **`planning`** is not defensible: nothing the planner chose was wrong.

**R5 verdict: REJECT.** Provenance good, lesson unsupported, class wrong.

---

## 3. R6 — the lesson misdescribes its own artifact

- Cited evidence is real (above).
- **But the artifact is a one-stage resume plan.** `plan_retry.json` contains exactly one stage,
  `target_box_b-1`, with `resumed_from_stage_ids: ["target_box_a-0"]`. The lesson opens *"A plan
  whose **second move** names an already taken destination..."* — **the cited plan has no second
  move.** It is the recovery attempt for a single remaining stage.
- **And the planner did not name a taken destination.** It named `[0.148,-0.150]`, which was free
  in the planned world and 56 mm from box a's planned spot. It became "taken" only because box a
  landed 9.65 mm off, putting the measured gap at 48.6 mm.
- The first clause is true — `completed_stage_ids: []` plus ec 60 from `prepare_plan` confirms the
  plan was rejected **before** it ran. That part is well evidenced. It is the inference
  (*"so the planner must choose a free one for each object"*) that does not follow: the planner
  already chose a free one.
- `recovery_decision.json` states the real situation: *"stages already committed; replay would
  contradict the measured world state. **A resumable plan is needed and is not implemented.**"*
  That is a capability gap in the recovery path, not a planning error.

### `failure_class: planning` is wrong here too

**`tooling`** (resume/recovery not implemented) or **`state`** (committed stages vs measured world
drift). Not `planning`.

**R6 verdict: REJECT.** Provenance good, lesson misdescribes the artifact and prescribes a remedy
the plan already applied, class wrong.

---

## 4. Is the verify.py change strictly stronger? **No.** Three defects, two demonstrated.

I replicated the exact assertion block from the new `verify.py:33-46` and ran it against the real
store plus synthetic records.

### 4a. The provenance gate is opt-in — omitting one field bypasses it entirely

```python
if r.get("provenance_verified") is True:     # line 40
```

I took a record whose evidence is pure fabrication —
`"detail": "the gripper spontaneously recited poetry and the task was abandoned"`, with an
invented lesson — and appended it **without** `provenance_verified`. **The gate passed it.**

```
=== ATTACK: append a FABRICATED record that does NOT claim provenance ===
  GATE PASSES  <-- fabricated record admitted
```

**The four legacy records carry no `provenance_verified` field.** They therefore still receive
**zero** provenance checking from this verifier — the exact defect the round set out to fix
remains open for them. The gate constrains records that volunteer; it does not require the claim.

### 4b. `is True` is a type check — the string `"true"` bypasses it

Same fabricated record with `"provenance_verified": "true"` → **gate passes**.

### 4c. `SEVEN` is six, and the missing field is `store_version`

```python
SEVEN = ("task_id", "failure_class", "evidence", "lesson", "source_run", "outcome")
```
That is **6** fields. The record's content schema has **7**: `store_version` is absent and
unchecked. The commit message and the code comment both say *"the seven content fields"*.
`len(SEVEN) == 6`. A record could be appended with no `store_version` and pass.

### 4d. `all(r["validated"])` was dropped with no replacement for non-claiming records

You are right that `all(validated)` asserted only that the seeder ran — that was my finding and
it was correct to remove. But removing it without requiring anything in its place means a record
with `validated: false` and no provenance claim now passes on six field names plus a directory
existence check. Under the **old** verifier that record failed. For that class the new check is
**weaker**, which is the opposite of what the commit claims.

### 4e. What the change genuinely gets right

Credit as due: when a record **does** claim `provenance_verified: true`, the re-verification runs
and it works — my fabricated record with `provenance_verified: True` was rejected with
*"fails re-verification: evidence not found in any machine-readable file"*. And relaxing
`== 4` to `>= 4` is correct: an exact count forbids an append-only store from growing.

**Honest summary:** it is stronger for cooperative records and weaker for uncooperative ones, and
it does not yet enforce the property on the records that failed review. The fix is small —
require `provenance_verified` to be present and boolean for **every** record (or derive it at
verify time rather than trusting the record), and add `store_version` to the tuple.

---

## 5. Correction to my own previous review: you were right about R3

I must put this plainly because I was the one who was wrong.

Last round I wrote that R3's evidence was *"genuine"*, found in `s1004-a1/task.out` and
`stack.log`, and I used that to say the record was traceable. **That was wrong.** There are three
directories named `s1004-a1`; my grep output had truncated paths to their last two segments, so I
attributed `evobot_t05_batch`'s `s1004-a1` lines to `evobot_t05_n6`'s `s1004-a1`.

- `evobot_t05_batch_20261111/runs/s1004-a1` → **domain 213** ✓ (where I read it)
- `evobot_t05_n6_20261111/runs/s1004-a1` → **domain 233** ← the record's actual cited source

Your checker is right and my sub-claim was wrong: the cited source does not contain `domain 213`.
**R3's rejection now stands on provenance as well**, not only on scope and class. My overall
REJECT verdict for R3 was right; my reasoning for trusting its evidence was not. This is the
second time this round I have been caught by two similarly-named artifacts being mistaken for one,
and the mechanical check caught what I did not — which is the argument for building it.

---

## 6. Overall verdict

**Neither of the two new records is review-grade. Do not build P4 on them.**

What improved is real and worth keeping: provenance is now mechanically checked, the cited strings
are genuinely in machine-readable run artifacts, `validated` is no longer falsely set, and a
fabricated *detail* string is rejected. That is a substantial step.

What did not improve is the harder half — **whether the record's diagnosis is true**. Both records
cite a real failure and then explain it as a planning error, when the artifacts show a correct
plan undone by execution accuracy against a margin smaller than the accepted tolerance. A record
that passes provenance but teaches the wrong lesson is more dangerous than one that fails
provenance, because it will be retrieved and acted on.

**P3 status: 0 of 6 records review-grade.** The two new ones are honest about provenance and wrong
about cause.

### Ranked fixes

1. **Make `provenance_verified` mandatory and boolean, or better, derive it at verify time**
   instead of trusting the record's own claim (4a, 4b). Without this the gate is advisory.
2. **Add the numeric fields to the provenance check** — `error_code` at minimum. Half of each
   record's meaning is currently unverified (section 1).
3. **Add `store_version` to `SEVEN`, or rename it `SIX`** (4c). A name that overstates the check
   is the same class of defect as `validated: true` set by the seeder.
4. **Have the lesson checked against the evidence's own numbers, not just its presence.** Both
   records here would fail: their numbers show a correct plan and a 1.4 mm margin shortfall.
5. **Split R5/R6 into what they actually evidence** — *"with a ±28 mm spread, a 9.65 mm placement
   error leaves 1.4 mm against a 50 mm clearance"* is a true, valuable, planner-adjacent finding.
   It is a `control`/`tooling` lesson, not a `planning` one.

One thing worth saying: the differential gate catching your own change at commit 10276211 is the
behaviour that makes this tractable. It rejected you, you recorded why, and an independent reader
could check it. That part of the machinery is working.
