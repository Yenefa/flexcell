# Re-grading the archives against a causally-connected observable: zero provable False Failures

**Date** 2026-11-12 · **Method** offline re-grade of all 238 archived runs · **Status: COMPLETE, and it NARROWS last round's claim**

---

## 0. What I set out to prove, and what I actually found

Round 3 established that `place_server` uses **gripper aperture** as its release predicate, and that the true
release is recorded in `carry.jsonl` (`cause: release`) while `place` reports `released: false`. The obvious
next step was to re-grade the archives against the causally-connected observable (the pin release) and
replace every contaminated execution number.

**I found zero provable False Failures.** My working criterion was necessary but not sufficient, and
checking it properly dissolved the claim rather than confirming it. That is the result and it is reported as
such.

## 1. The census (this part stands)

All 238 archived run directories under `setup/acceptance/` that have `skills/carry.jsonl`, across 21
experiment archives:

```
runs scanned                              : 238
runs with a place 'gripper did not open'  :  47   (19.7 %)
  ...in which the carry STILL released    :  47   (100 %)
runs where a carry was ever left held     :   0
```

Two facts are firm:

1. **The defect is present in 47 of 238 archived runs (19.7 %)** — consistent with the 19 % place-attempt rate
   measured in round 3.
2. **The carry mechanism never once failed to release.** Across 238 runs and every `start` event, releases =
   starts in all of them. A carry that fails to release does not occur in this archive.

## 2. The step where my reasoning broke

I took "every plan stage released, nothing stuck" as sufficient for "the run's failure verdict is false".
**It is not.** Release is not placement. An object can be released perfectly and still be in the wrong
place, and the task clauses grade *where it ended up*, not whether it was let go of.

Cross-tabulating the 47 runs against their recorded verdicts:

| recorded verdict among the 47 | count |
| --- | --- |
| recorded **PASS** | **28** |
| recorded **FAIL** | 11 |
| no `verdict.json` (graded elsewhere) | 8 |

**28 of the 47 passed anyway.** The defect was present in the logs and did not determine the verdict. So
even before checking the 11 failures, the defect is clearly not a verdict-corruptor on its own.

## 3. I tested every candidate and all of them are GENUINE failures

Of the 11 recorded failures, five satisfied my (too weak) criterion. I checked all five against the failed
clause evidence and the ground truth:

| archive | run | failed clause | ground truth | verdict |
| --- | --- | --- | --- | --- |
| `evobot_goal_check_ab_20261111` | HO-2f52569ef5ca | `placement:target_box_b` | box_b at **[0.2, −0.18] = its initial pose**, 0.235 m from zone_2 | **GENUINE** |
| `evobot_pooled_n32_20261111` | HO-b6d9e15b2431 | `placement:target_box_b` | box_b at **[0.2, −0.18] = its initial pose**, 0.235 m from zone_2 | **GENUINE** |
| `evobot_native_honesty_20261111` | HO-38ce6531a597 | `visit_sequence:target_box_b` | observed `[zone_1, zone_2]` vs required `[zone_1, zone_2, zone_1]`; box_b never delivered | **GENUINE** |
| `evobot_unseen_bc_20261111` | HO-42109d30fa00_B | `visit_sequence:target_box_a` | sequence incomplete; **box_b still at its initial pose** | **GENUINE** |
| `evobot_unseen_n6_20261111` | HO-fd5737f932db_B | `visit_sequence:target_box_b` | sequence incomplete | **GENUINE** |

**Every one is a real failure.** In three of them an object never moved from its start pose — the task was
not performed, whatever the gripper did. In two the required visit sequence has a missing leg.

## 4. The corrected claim

| claim | status |
| --- | --- |
| the `place` release defect exists and is frequent | **CONFIRMED** — 47/238 archived runs, 19.7 % |
| the carry never fails to release | **CONFIRMED** — 238/238 runs, releases = starts |
| the defect produces provable False Failures in the archives | **NOT SUPPORTED — zero found** |
| the defect corrupts **task-level** verdicts | **NO.** Task clauses grade final world positions, which are correct |
| the defect corrupts **execution** verdicts | **YES.** This is where its harm is confined |

**So round 3's "the world is right and the verdict is wrong" holds for the *execution* verdict, not the
*task* verdict.** The 4-run gap between A-prime's 9/16 execution and its 13/16 evaluation is exactly this:
those four runs were reported as executor failures while the objects ended in the right places and the task
clauses passed. The task-level numbers across the archive are **not** contaminated, which is a narrower and
better-supported conclusion than the one I set out to prove.

## 5. Why this matters more than the claim it replaced

Round 3 said every execution-based success rate in the project's history is an underestimate. **That is
correct but it is only about execution verdicts.** The stronger-sounding version — that the project's
*results* are contaminated — is **false**, and I nearly published it. The distinction is:

```
execution_succeeded   : contaminated, understated by the defect
independent_evaluation_passed : NOT contaminated, reads the world
```

Which is the same separation the mission demanded from the start, arrived at from the other direction: the
four states are separate because they are measured by different paths, and one of those paths is broken.

## 6. What I could not establish

- **8 of the 47 have no `verdict.json`** — graded in an external harness. I did not chase those, so the
  count of affected *verdicts* is over 39 runs at most, not 47.
- I checked the 5 candidates that met my criterion. The other 6 recorded failures did not meet it (release
  was incomplete), so they are genuine by construction — but I did not verify each individually.
- "Provable False Failure" here means *recorded fail, all stages released, and the failed clause is
  contradicted by the ground truth*. I found none. A false failure with a different signature would not
  have been caught by this method.

## 7. Reproduce

```bash
python3 setup/acceptance/evobot_lead_historical_regrade_20261112/regrade_archives.py
```

Offline, no simulator. The script prints the census, the cross-tab, and then tests every candidate against
**the failed clause's own evidence and the ground truth** — not against the release count, which is the
mistake this document records.
