# The provenance check now verifies numbers — the reviewer's demonstration is closed

**Date** 2026-11-12 · **Status: Implemented → Unit Tested (11/11) → shown against the six real records**

---

## 1. The hole, exactly as the reviewer demonstrated it

`evidence_strings()` kept only strings of 8+ characters. **Every number was skipped.** The consequence:

> Feeding it `error_code 99` instead of the true 60 still **PASSED**. `ec 61` vs `60` was the only thing
> separating the two records, and it was unverified. They happened to be right because they were written
> honestly, not because the check established it. Swap them and you get two provenance-passing wrong records.

— round-15 independent review

**A check that verifies the evidence but not its numbers is not verifying the evidence.**

## 2. Why a substring test would not have fixed it

The obvious repair — search for the number as text — is wrong. `60` occurs in timestamps, coordinates and
port numbers; a substring hit proves nothing. So numeric and boolean facts are checked **structurally**:
they must match a **typed field value in a parsed JSON object**.

```python
for obj in _json_objects(path):          # .json and .jsonl, parsed
    for key, value in scalars:
        if _matches(obj.get(key), value):   # exact typed equality
            hits[key] = path
```

`_matches` refuses to treat a boolean as an integer, so `True == 1` cannot smuggle a wrong fact through.

## 3. Tests: 11/11, built from the reviewer's own corruptions

```
evidence in a JSON log -> ACCEPT                     PASS
evidence only in README -> REJECT                    PASS
source_run missing -> REJECT                         PASS
correct error_code 60 -> ACCEPT                      PASS
CORRUPTED error_code 99 -> REJECT                    PASS
CORRUPTED outcome 0 (not in file) -> REJECT          PASS
error_code 0 as substring only -> REJECT             PASS
error_code as STRING not int -> REJECT              PASS
one evidence string missing -> REJECT                PASS
planner lesson -> ACCEPT                             PASS
harness lesson -> REJECT                             PASS
```

Two of these exist **specifically** to prove the fix is structural rather than textual:

- `error_code 99` — the reviewer's exact demonstration. Now rejected.
- `error_code 0 as substring only` — the fixture contains `60`, which **contains** `0`. A substring test
  would accept it. The structural test rejects it.

One pre-existing test had to change: *"evidence is all numbers -> REJECT"* was asserting the **old, wrong**
behaviour. Numbers are verifiable now, so its premise was obsolete rather than its expectation.

## 4. Against the six real records

```
T01-train-seed1000             FAIL   evidence not found in any machine-readable artifact
T05-train-seed1000             FAIL   ...
T05-train-seed1004             FAIL   ...
T03-heldout-seed9000           FAIL   ...
T05-recover-occupied-stage     PASS   all 2 evidence fact(s) located
T05-recover-declared-occupied  PASS   all 2 evidence fact(s) located
```

The two records whose evidence is genuine still pass **with their error codes checked**, not merely their
detail strings. The four legacy records still fail, as they should.

## 5. What this does not fix, and I am not papering over it

The reviewer's **fix 4** remains open and it is the one that matters most:

> *"Check the lesson against the evidence's own NUMBERS, not just its presence. Both records fail that:
> their numbers show a correct plan and a 1.4 mm shortfall."*

Provenance now proves **the failure happened and what its code was**. It does **not** prove the lesson
follows from it. Both rejected records would still pass every check in this file — their evidence is real,
their error codes are real, and their lessons are still false. **What caught them was a human-readable
review, not a check**, and no check I have written would have caught them.

## 6. Why I did not write a corrected record this round

The reviewer supplied the true finding: *"with a ±28 mm spread, a 9.65 mm placement error leaves 1.4 mm
against a 50 mm clearance"* — a control/tooling fact, not a planning lesson. It would be a defensible record.

**I did not add it.** Authoring another lesson before the check exists that can catch a false one is exactly
how round 14 produced two confidently-worded wrong records. The store stays at 6 records, 2 provenance-verified,
**0 review-grade**, and retrieval returns 0 lessons. That is the honest state and it is not improved by
adding a seventh unverified claim.

## 7. Reproduce

```bash
python3 evolution/experience/test_verify_provenance.py    # 11/11
```

---

## 8. Review is now FAIL-CLOSED — no verdict means no retrieval

The reviewer's sharpest sentence was: *"a record that fails provenance gets rejected; a record that passes
provenance and teaches the wrong lesson gets retrieved and acted on."* Round 15 fixed half of it — a REJECT
now stops a lesson — but a record with **no verdict at all** was still retrievable, which is exactly the window
round 14's false lessons passed through before anyone reviewed them.

**A record needs an explicit independent `ACCEPT` before it may influence a plan.** Absence of a verdict is
absence of approval, not the benefit of the doubt.

```
no review ledger -> NOT retrieved                    PASS  0 lesson(s)
independent ACCEPT -> retrieved                      PASS  1 lesson(s)
independent REJECT -> NOT retrieved                  PASS  0 lesson(s)
ACCEPT for another digest -> NOT retrieved           PASS  0 lesson(s)
corrupt ledger -> NOT retrieved (fail closed)        PASS  0 lesson(s)

5/5 tests passed
```

The last two matter: an `ACCEPT` recorded against a **different** record's digest must not approve this one,
and a **corrupt** ledger must fail **closed** rather than open. A review gate that fails open on a parse
error is not a gate.

Effect on the live store: **retrieval returns 0 lessons for every template**, because neither
provenance-verified record carries an `ACCEPT`. That is the correct result — both were independently rejected
— and it is now enforced rather than merely true.

## 9. The full state after this round

| property | status |
| --- | --- |
| evidence must be findable in a machine-readable artifact | **enforced** |
| evidence **numbers** must match a typed field value | **enforced (new)** |
| a lesson the planner cannot act on is refused at write time | **enforced** |
| a REJECT stops a lesson reaching a plan | **enforced** |
| **no ACCEPT means no retrieval** | **enforced (new)** |
| a lesson is checked to **follow from** its evidence | **NOT enforced, NOT automated** |
| the store holds a review-grade record | **no — 0 of 6** |

The sixth row is the one that matters and it is the one no check here addresses. Every mechanical property
is now fail-closed; the semantic property — *does this lesson follow from this evidence* — is still caught
only by a reviewer reading it. **I would rather say that plainly than add a seventh check that appears to
cover it.**