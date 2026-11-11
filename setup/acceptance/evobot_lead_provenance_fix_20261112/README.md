# The ten-line fix, applied: the seeder now checks evidence instead of asserting it

**Date** 2026-11-12 · **Status: Implemented → Unit Tested (7/7) → demonstrated against the real seeds**
**Files changed: `evolution/experience/seed_from_evidence.py`, new `verify_provenance.py`, new test. None are pinned.**

---

## 1. The defect, in one line of code

`seed_from_evidence.py` used to say:

> *"Every record points at an archived run directory that still exists. The evidence is copied from what
> the run actually logged. Nothing here is a recollection."*

And it implemented that as:

```python
if not source.exists():        # line 26 — the only check
    print('SKIP (no archived evidence):', s['source_run'])
    continue

rec['validated'] = True        # line 31 — set by the seeder itself
```

**It never opened the directory.** A record passed if a *path* existed, regardless of whether the evidence
was anywhere inside it. The independent review in round 12 found that 3 of 4 such records cite evidence their
own source cannot contain, because the archive holds the **post-fix** run while the evidence describes the
**pre-fix** failure.

## 2. The fix

New `evolution/experience/verify_provenance.py`:

| function | rule |
| --- | --- |
| `verify_provenance(source_root, evidence)` | **every** string in the evidence must appear in a **machine-readable** file under `source_run` |
| `check_actionability(lesson, repo_root)` | refuses `HARNESS` / `DOWNSTREAM_CODE` / `UNCLEAR` lessons **at write time**, reusing the existing `audit_actionability` classifier |

**Prose is excluded by suffix** (`.md`, `.rst`, `.txt`). A README that narrates a run is a *claim about a
measurement*; the check requires the measurement.

**Fail-closed on four paths**: missing source directory, evidence with no verifiable string, any single
evidence string not found, and a lesson the planner cannot act on. Silence is never read as success — that
is precisely how the previous version passed three bad records.

## 3. Demonstration against the four real seeds

```
$ python3 evolution/experience/seed_from_evidence.py --dry-run
REJECT T01-train-seed1000       PROVENANCE: evidence not found in any machine-readable file under source_run: detail
REJECT T05-train-seed1000       PROVENANCE: evidence not found in any machine-readable file under source_run: detail
REJECT T05-train-seed1004       PROVENANCE: evidence not found in any machine-readable file under source_run: failure
REJECT T03-heldout-seed9000     PROVENANCE: evidence not found in any machine-readable file under source_run: detail

accepted: 0   rejected: 4   (dry_run=True)
```

**4 of 4 rejected, not 3 of 4.** The review expected R3 to survive because it believed R3's evidence was in
real run logs. My round-12 audit recorded a disagreement there: the record says **domain 213** and
`runs/s1004-a1/stack.log` says **domain 233**. The mechanical check tests the exact cited string and therefore
rejects R3 as well. **The disagreement is now settled by a check rather than by argument**, and it settled
against the review's more generous reading.

This is a stronger result than predicted and it is not a better one for the project: **the experience store
cannot currently be reseeded from its own seed file at all.** That is the honest state.

## 4. Tests

```
test                                                 result
----------------------------------------------------------------------------------------
evidence in a JSON log -> ACCEPT                     PASS
evidence only in README -> REJECT                    PASS
source_run missing -> REJECT                         PASS
evidence has no verifiable string -> REJECT          PASS
one evidence string missing -> REJECT                PASS
planner lesson -> ACCEPT                             PASS
harness lesson -> REJECT                             PASS

7/7 tests passed
```

The cases were chosen for where a naive check passes: **case 2 is the actual historical defect**, and cases 3
and 4 are the ways a check can look like it ran while checking nothing.

## 5. What changed in the record schema, conservatively

| field | before | after |
| --- | --- | --- |
| `validated` | seeder set it `True` | **seeder leaves it `False`** — not the seeder's to set |
| `provenance_verified` | absent | **`True` only when the evidence was located in a machine-readable file** |
| `evidence_files` | absent | **the files the evidence was actually found in** |
| `reviewed_by` / `review_verdict` / `review_ref` | absent | present and `None` — for the reviewer, not the seeder |

I did **not** rewrite `records.jsonl` and did **not** re-seed. The four existing records keep `validated: true`
because that field now records a historical fact (the old seeder ran); changing them would destroy evidence of
the defect this round is documenting.

## 6. What this does and does not fix

| claim | status |
| --- | --- |
| the seeder can no longer accept narration as evidence | **FIXED, tested** |
| harness lessons are refused at write time | **FIXED, tested** |
| `validated` no longer means "the seeder ran" | **FIXED for future records only** |
| the four existing records are repaired | **NO** — they cannot be; their cites do not contain the evidence |
| the experience channel now works | **NO.** The store is empty of trustworthy records and cannot be reseeded. Three of the review's five ranked fixes remain open (source_run pointing at the run, archiving the failing run, and a reviewer-owned verdict workflow) |

**This makes P3's channel honest, not functional.** An empty store that refuses bad records is a better
foundation than a populated one that accepts them, but it is not experience reuse.

## 7. Reproduce

```bash
python3 evolution/experience/test_verify_provenance.py          # 7/7
python3 evolution/experience/seed_from_evidence.py --dry-run    # 0 accepted, 4 rejected, writes nothing
```
