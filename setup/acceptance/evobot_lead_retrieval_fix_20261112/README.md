# Retrieval was blind to the only trustworthy records — the channel was empty for a second reason

**Date** 2026-11-12 · **Status: fixed, measured against the frozen unseen templates.**

---

## 1. The defect, in one filter

`experiments/baselines/baseline_c.py` line 49:

```python
rows = [r for r in store.read(store_path) if r.get("validated")]
```

`validated` is set **by the seeder**. An independent review found that **3 of 4** records carrying it cite
evidence their own cited source cannot contain. And after the round-13 provenance guard landed, a record that
had **actually been checked** carries `validated: False` and `provenance_verified: True`.

**So the filter hid the two trustworthy records and admitted the four a reviewer had rejected.**

Measured, on a relay-style instruction, before the fix:

```
retrieve() returned 1 lesson:  T01-train-seed1000   validated=True  prov=None
the two provenance-verified records are retrievable?  False
```

This is the third instance of the same stale filter (audit_actionability, the Baseline C verifier, and now
the retrieval path) — and the only one that actually stood between a verified lesson and a plan.

## 2. The fix

```python
all_rows = store.read(store_path)
verified = [r for r in all_rows if r.get("provenance_verified") is True]
rows = verified if verified else [r for r in all_rows if r.get("validated")]
```

**Verified records only.** The legacy field is a **fallback for stores that have no provenance information
at all**, not a preference — so an old store keeps its old behaviour, while any store that has been verified
stops feeding unverified lessons into plans.

## 3. What it changed, measured on the frozen unseen templates

| instruction | retrieved before | retrieved after |
| --- | --- | --- |
| **T12 triple revisit** | 1 legacy lesson | **2 verified lessons** |
| **T13 geometric conditional** | 1 legacy lesson | **2 verified lessons** |
| **T14 ordered pair** | 1 legacy lesson | **2 verified lessons** |
| T05 relay | 1 legacy lesson | **2 verified lessons** |

Both lessons score on `_REQUIRED_FIELDS` (they name an object and a zone), so they retrieve for **every**
instruction rather than by keyword luck. The Baseline C verifier now reports `retrieved_lessons: 2` where it
reported 1.

## 4. What this does NOT establish, and it is the whole of P4

**Retrieval is not influence.** `build_observation_with_experience` attaches the lessons to the observation as
an `experience` field. Whether a plan changes depends on the planner consuming that field:

| arm | consumes `experience`? |
| --- | --- |
| A (rule-based) | no — deterministic rule planner, ignores the field |
| B (model planner) | yes, if the prompt includes it |
| C | **the point of C** |
| D | undefined (`BLOCKED_MISSION_TEXT_MISSING`) |

So the honest statement is:

> **The experience channel now reaches the frozen unseen tasks.** Two provenance-verified, planner-actionable
> lessons are retrieved for T12, T13 and T14. **Whether their presence changes any plan is unmeasured**, and
> D — the arm that would test cross-task reuse — remains undefined.

**The P4 verdict therefore stays `EVOLUTION_ADVANTAGE_NOT_DEMONSTRATED`,** but its reason has changed twice in
three rounds and each time got narrower:

| round | reason |
| --- | --- |
| 12 | the channel had no lesson that could act on any task (1/4 actionable, about an error that never occurs) |
| 14 | verified lessons exist and are actionable, but retrieval filtered them out |
| **15** | **retrieval works and reaches the unseen tasks — what is missing now is evidence that a plan consumes it, and an arm to compare** |

## 5. What I did not do

- **Did not run B or C.** Doing so needs the paid model entry `ci-public-window/scripts/evobot_llm_key.sh` and
  would be a real spend decision, not a measurement I should take unilaterally mid-round.
- **Did not weaken the retrieval rule** to make it look productive. Verified-only is stricter than the
  original, and the legacy fallback preserves old-store behaviour rather than granting it new trust.
- **Did not touch thresholds, evaluators, or the frozen unseen task set.**

## 6. Reproduce

```bash
python3 setup/acceptance/evobot_lead_retrieval_fix_20261112/show_retrieval.py
```

Prints, for each of the three frozen unseen template instructions and the T05 relay instruction, how many
lessons retrieval returns and which records they came from — with the arm that consumes the field named
beside each.