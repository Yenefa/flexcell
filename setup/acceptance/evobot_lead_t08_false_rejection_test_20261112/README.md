# Is T08's 0/6 a false-rejection artifact? No — and my first pass said yes because I read the criterion wrong

**Date** 2026-11-12 · **Method** offline: grade every unseen push against all four sub-clauses of the frozen criterion
**Status: hypothesis tested and largely REFUTED. One genuine false rejection found. FALSE SUCCESS = 0.**

---

## 1. The hypothesis, and why it was worth testing

Rounds 3–5 found two defects of the same shape: **a skill's internal precision contract used as a binary success
verdict, when the world had already satisfied the task.** The `place` release predicate rejected a release the
carry backend had confirmed. So the obvious next question:

> Is T08's reported 0/6 the same thing — a skill rejecting pushes that physically satisfied the task?

It was worth asking because two earlier held-out passes came from motion the skill had *rejected*
(`U_shot/seed3000` `ec=36`, `U_shot/seed3002` `ec=28`).

## 2. My first pass said yes. It was wrong.

I graded 23 archived push records against the displacement band, the vertical bound and the direction
cosine, and got:

```
records satisfying the criterion independently : 8 of 23
  ...that the SKILL reported failure          : 6
```

A 75 % false-rejection rate. That looked like a major finding.

**I had omitted a sub-clause.** `benchmark/evaluators/evaluate.py:199-210`:

```python
if want.get("zone"):
    d = _dist2d(end, zones[zn]["pose"])
    zone_ok = d <= zones[zn]["radius"]
```

The task requires the block to **end inside `zone_push`** (radius 0.06 m). Every T08 spec declares it. I did
not check it. Grading against a partial reading of the criterion is the same error class this project keeps
recording, and I walked into it while looking for it.

## 3. With all four sub-clauses

Unseen evidence records (the set that matters for generalisation), graded against the complete criterion:

| record | out | ec | disp | cos | dz | zone_d | radius | ALL4 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `U/seed3000/t1` | 1 | 36 | 0.1561 | 1.000 | 0.0017 | 0.0532 | 0.06 | **FAIL** — disp > 0.150 |
| `U/seed3001/t1/00` | 1 | 28 | 0.0514 | 0.992 | −0.0000 | 0.0858 | 0.06 | **FAIL** — outside zone |
| `U/seed3001/t1/01` | 1 | 36 | −0.0654 | −1.000 | −0.0006 | 0.2540 | 0.06 | **FAIL** — wrong direction |
| **`U/seed3002/t1`** | 1 | **36** | **0.1480** | **1.000** | **0.0028** | **0.0294** | **0.06** | **PASS** |
| `U_shot/seed3000` | 1 | 28 | 0.0179 | 0.999 | −0.0000 | 0.0971 | 0.06 | **FAIL** — under 0.030, outside zone |
| `U_shot/seed3001` | 1 | 28 | 0.0140 | 1.000 | −0.0001 | 0.1033 | 0.06 | **FAIL** — same |
| `U_shot/seed3002` | 1 | 27 | −0.0001 | −0.027 | 0.0000 | 0.1322 | 0.06 | **FAIL** — no contact |

```
unseen records graded              : 7
satisfy ALL FOUR sub-clauses       : 1
  ...that the SKILL reported failure : 1   (one false rejection)
skill claimed success but failed   : 0   (FALSE SUCCESS - target is 0)
```

**The hypothesis does not hold.** Six of the seven failures are genuine: the block did not reach the zone,
or it moved the wrong way, or there was no contact at all. **T08's 0/6 is a real capability gap, not a
measurement artifact.**

## 4. The one false rejection is real, and it is the same defect shape

`U/seed3002/t1`: the block moved **0.1480 m** along the required direction (task band allows up to **0.150**),
ended **0.0294 m** from the zone centre (inside the 0.06 radius), and did not lift (dz 0.0028 m). **The task
was satisfied.**

The skill reported `ERR_DISPLACEMENT_OVERSHOOT` because it had **requested 0.0900 m** and the block moved
0.1480 m — an error of 0.0580 m against a `displacement_tolerance_m` of **0.005 m**.

| criterion | accepts |
| --- | --- |
| task's frozen push clause | displacement in **[0.030, 0.150]** *and* inside the zone |
| skill's own verdict | displacement within **±0.005 m of the requested distance** |

**The skill is 12× stricter than the task, on a different quantity** (distance from a request, not membership
of a band). So a push that demonstrably completed the task is reported as a failure.

This is the third instance of one shape:

| # | skill | internal contract | task reality |
| --- | --- | --- | --- |
| 1 | T08 push gate (round 2) | aperture travel means a grasp | 0.42 mm from closing on air |
| 2 | `place` release (rounds 3–4) | aperture means a release | carry confirmed the release |
| 3 | T08 push verdict (this round) | within 5 mm of the **requested** distance | task accepts a **band** |

**But the magnitude here is small and I want to be precise about it: 1 of 7, not 6 of 7.** The first two were
systematic (37.5 % of runs, 100 % of place failures). This one is a single case, and fixing it would move T08
from 0/7 skill-certified to 1/7 — not from 0 to 6.

## 5. What T08's numbers actually are, stated separately

The mission requires four separate states. For the unseen set:

| state | value |
| --- | --- |
| `planning_correct` | not re-measured this round — **UNKNOWN** |
| `execution_succeeded` (task criterion, push clause only) | **1 of 7** |
| `independent_evaluation_passed` (whole task, all clauses) | **2 of 6** from the earlier held-out run — a different denominator; not reconciled here |
| `agent_claimed_success` | **0 of 7** |
| **False Success** | **0** |

**The fail-closed property the mission demands holds**: the skill never claimed a success it did not achieve.
That is the one thing 0/6 was supposed to guarantee, and it is true.

## 6. What this changes

- **T08 remains a genuine capability gap.** The push skill cannot reliably deliver the block into the zone —
  6 of 7 unseen attempts failed physically, most by falling short (0.014–0.051 m against a 0.030 m minimum and
  a zone 0.086–0.103 m away).
- **The blocker is reach, not verification.** The verification layer is not manufacturing the failures.
- **The overshoot rule is worth revisiting separately**, and it is the *only* false rejection found. But it is
  not what is standing between this project and T08.
- **The real target is displacement**: the block must travel ~0.09–0.11 m into the zone, and the skill's reach
  error and contact-loss behaviour stop it around half that. That is the same contact-geometry problem the
  height calibration exposed, and it is not solved by a verdict change.

## 7. Reproduce

```bash
python3 setup/acceptance/evobot_lead_t08_false_rejection_test_20261112/grade_unseen_all_four.py
```

Offline. Reads the committed evidence records and the task specs; grades all four sub-clauses and reports
false rejections **and false successes** separately.
