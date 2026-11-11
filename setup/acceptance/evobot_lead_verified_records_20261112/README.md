# The fixed pipeline accepts: two provenance-verified, planner-actionable records

**Date** 2026-11-12 · **Status: the store gained its first mechanically-verified records**

---

## 1. Round 13 ended with an honest but empty channel. This round fills it correctly.

The provenance fix rejected **all four** legacy seeds. That was the right outcome, but it left the store with
nothing trustworthy and no way to reseed. The remaining question was whether the fixed seeder can accept a
**genuine** record — and if it cannot, the channel is dead rather than strict.

## 2. What I looked for

A planner-level failure whose evidence exists in a **machine-readable** file. Searching every `*.jsonl` in
the archive for planner-class error codes (60, 61, 63, 64) carrying a `detail` string:

```
planner-code failures with a machine-readable detail string: 2 distinct, 5 total

  ec=61  n=3  'state drift or occupied destination before target_box_b-1'
  ec=60  n=2  'declared destination occupied at target_box_b-1'
```

Both live in `evobot_recover_n6_20261111/runs/HO-90899d657e68/sim/skills/composites/*.jsonl` — real logs, not
prose. **The failure the legacy record R4 claimed is real.** R4 cited the wrong source and the wrong code
context, but the event happened and here is the citation.

## 3. Two genuine seeds, accepted

| seed | class | evidence | lesson |
| --- | --- | --- | --- |
| `T05-recover-occupied-stage` | planning | `error_code 61`, detail string | *"Before sending a second object into an area, check that area is still free; order the moves so a later stage is not blocked by an earlier one."* |
| `T05-recover-declared-occupied` | planning | `error_code 60`, detail string | *"A plan whose second move names an already taken destination is rejected before it runs, so the planner must choose a free one for each object."* |

```
$ python3 evolution/experience/seed_from_evidence.py --append --seeds evolution/experience/seed_evidence_verified.json
ACCEPT T05-recover-occupied-stage     provenance + actionability ok
ACCEPT T05-recover-declared-occupied  provenance + actionability ok
accepted: 2   rejected: 0
chain intact (6 records)
```

And the evidence files resolve, checked afterwards rather than assumed:

```
T05-recover-occupied-stage     file_exists=True  evidence_present=True
T05-recover-declared-occupied  file_exists=True  evidence_present=True
```

## 4. I broke a downstream filter, and fixed it

`audit_actionability.py` filtered on `validated`. After the provenance fix that field means **"the old seeder
ran"** and no longer means trustworthy — so the audit silently reported on the 4 **least** trustworthy records
and ignored the 2 verified ones. **A filter whose meaning changed under it.**

It now partitions by `provenance_verified` and reports both cohorts, because one blended number hid which half
of the store the conclusion applied to.

## 5. The result changes what P4 can say

```
=== VERIFIED cohort (provenance checked mechanically) ===
  ACTIONABLE FRACTION (verified): 2/2

=== UNVERIFIED cohort (legacy) ===
  ACTIONABLE FRACTION (unverified): 1/4

=== combined ===
  total records: 6
  ACTIONABLE FRACTION (all): 3/6
```

**Every verified record is planner-actionable; most unverified ones are not.** So the defect was in the
**seeding**, not in the concept — which is the most useful thing this round establishes.

| P4 statement | round 12 | now |
| --- | --- | --- |
| lessons that could act on a plan | 1 of 4 | **2 of 6 overall, 2 of 2 among verified** |
| the failure they address occurs machine-readably | **no** (ec=64 appears nowhere) | **yes — ec 60/61, 5 occurrences in real logs** |
| evidence re-derivable from the cited source | 0 of 4 | **2 of 6; 2 of 2 among verified** |
| therefore | "a D arm has nothing to reuse" | **"a D arm now has two actionable lessons about a failure that really occurs; whether they change behaviour on frozen unseen tasks is still unmeasured, and D is still undefined"** |

**I am not claiming P4 is closer to passing.** Two lessons about an occupied-destination failure may simply
never arise on the frozen unseen task set. What changed is that the channel is no longer empty for a
*structural* reason — further work on P4 now tests a mechanism that exists rather than one that cannot.

## 6. What is still wrong, stated plainly

- **`validated` is still `True` on the four legacy records** and still does not mean reviewed. The new records
  carry `validated: False` and `provenance_verified: True`; the old ones carry the opposite pattern. Two
  conventions now coexist and the field name remains misleading.
- **No human or independent reviewer has signed either new record.** `reviewed_by`, `review_verdict` and
  `review_ref` are present and `None`. Provenance verification is not review, and I am not going to let the
  word do double duty — that was precisely the round-12 finding.
- **`source_run` still points at a run directory, not at a single run artifact.** Fix 2 of the review's five
  is still open; the new seeds point at `runs/HO-...` which is better than a batch directory but not a file.

## 7. Reproduce

```bash
python3 evolution/experience/seed_from_evidence.py --dry-run --seeds evolution/experience/seed_evidence_verified.json
python3 evolution/transfer/audit_actionability.py      # verified 2/2, unverified 1/4
```
