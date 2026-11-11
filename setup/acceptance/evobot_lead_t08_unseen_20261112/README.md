# T08 on unseen instances: **0 of 6** — the first generalisation measurement, and it is negative

**Date** 2026-11-12 · **Produced by** the simulation lane · **Verified by** the Lead
**Status: CONFIRMED. This is the decisive result about scope.**

---

## 1. The headline

Six trials on the three frozen unseen instances (`t08_unseen` seeds 3000/3001/3002), two arms:

```
arm      seed      terminal  passed  displacement  failure class
U        seed3000  false     false   147.45 mm     FAIL_OVERSHOOT
U        seed3001  false     false   166.21 mm     FAIL_DIRECTION
U        seed3002  false     false   118.05 mm     EVIDENCE_INCOMPLETE
U_shot   seed3000  false     false    45.79 mm     FAIL_DIRECTION
U_shot   seed3001  false     false    76.41 mm     FAIL_DIRECTION
U_shot   seed3002  false     false    54.82 mm     FAIL_DIRECTION

unseen trials: 6   terminal_passed: 0   passed: 0
```

**0/6.** The one dev-instance pass (S/t3) **does not transfer**.

## 2. Why this is the round's most important number

The dev instance (seed 2000) produced **1 pass in 9 valid trials**. The three unseen instances produced
**0 in 6**. Whatever produced that single pass on seed 2000 is **not** a capability that survives a change
of initial pose.

This is exactly why the mission separates `Simulation Tested` from `Generalization Tested`, and it is the
measurement that prevents the round from over-claiming. Without these six runs, "T08 produced a
`passed=true`" would be the whole story, and it would be misleading.

## 3. The failures are genuine, not artifacts — checked deliberately

The round had just found a recorder defect that invalidates a whole bundle when any contact lasts exactly
one physics step, so the first thing I checked was whether U's failures were that defect rather than robot
failures:

| Seed | Zero-span contact intervals | Schema problems | Verdict |
| --- | --- | --- | --- |
| seed3000 | **3** | 3 | bundle invalid **and** terminal genuinely failed (`unmoved` clause: blue block moved 0.030 m vs 0.015 tol) |
| seed3001 | **1** | 1 | bundle invalid **and** terminal genuinely failed (166.21 mm, cos −0.89) |
| seed3002 | 0 | 0 | bundle **valid**; terminal failed on `unmoved` (blue block moved 0.050 m vs 0.015 tol) |

**The defect recurred on unseen data (2 of 3 recovery trials) — the exact failure I predicted when I wrote
it up — but it destroyed no pass.** In both affected runs the terminal clause was already failing on an
independent ground: the protected blue block had been moved. So the correct labels are:

- seed3000 / seed3001: **terminal failure + invalid evidence** (both true; the physical failure is proven
  by the `unmoved` clause, which does not depend on the bundle)
- seed3002: **terminal failure + valid evidence** — a clean, fully-evidenced negative

**This is the difference between "we could not measure" and "we measured and it failed."** Two of the six
are the former only for the evidence gates, never for the terminal clause.

## 4. What the failures say about the physics

**4 of 6 unseen trials ended with negative direction cosine** — the block driven backwards. Across the
whole round (dev + unseen, 15 valid trials) `FAIL_DIRECTION` is the dominant class:

| Class | Count (all arms, valid trials) |
| --- | --- |
| `FAIL_DIRECTION` (cos < 0, pushed backwards) | **8** |
| `FAIL_LIFT` | 1 |
| `FAIL_ZONE` / `FAIL_OVERSHOOT` | 3 |
| `GATE_GRIPPER` | 1 |
| **PASSED** | **1** |

The unseen instances make it worse, not better: **the strategy is not merely unreliable on one pose, it is
unreliable in the same specific way everywhere** — the end effector does not maintain a stable contact face,
and whether the block goes forward or is flicked backwards depends on the contact instant.

## 5. Consequences for every claim in the round

| Claim | Effect |
| --- | --- |
| "T08 produced its first `passed=true`" | **STILL TRUE** — S/t3 is real and verified |
| "T08 is a usable capability" | **REFUTED MORE STRONGLY** — 0/6 unseen |
| "T08 is Generalization Tested" | **NO — and now we know it fails generalisation** |
| "The single pass shows the approach works" | **NO — it shows one pose out of four tried admits a pass** |
| "The recovery strategy generalises" | **NO** — 0/3 unseen; and it was 0/5 on dev |
| "T08 deserves more tuning on dev" | **NO** — dev tuning already produced 1/9; more dev tuning would fit the one instance |

**The correct level remains `Simulation Tested` on a single dev instance.** The mission's ladder says
`Generalization Tested` requires success on **frozen unseen tasks**; six unseen trials produced zero. The
project now has a **measured negative generalisation result**, which is worth more than an unmeasured claim.

## 6. What this means for the next round

The next experiment is **not** more T08 trials. It is the same one this round's audit pointed at:
**fix the contact geometry, then re-measure.** Specifically:

1. **The G1/G2/G3 gripper calibration** (`evobot_lead_gripper_gate_adjudication_20261112/` §6) — 2 runs,
   no model calls, and it decides whether the round's best trial was wrongly rejected.
2. **Then a contact-geometry change** — the backwards flick is a physical mechanism, and no retry policy
   addresses it. Candidates: derive the contact height from object geometry rather than a constant;
   command a link that has collision geometry; a single-finger push.
3. **Then re-measure on unseen with a larger n.** n≈9.5 per arm is the threshold for ordering two arms at
   80 % vs 20 %; the round has 1 pass in 15 valid trials overall, so the honest expectation after a geometry
   fix is a different number, not a better one.

**Do not run more dev-instance trials first.** That is how the single pass happened, and repeating it would
fit the instance rather than the task.

## 7. Provenance

Produced by the simulation lane on the frozen unseen specs
(`benchmark/tasks/t08_unseen/T08-push-seed{3000,3001,3002}.json`, split `t08_unseen`, never used for
development). Policy frozen before the run; `git HEAD` and script hashes recorded in the batch manifest.
No parameter was changed after U began. Verdicts from `evaluate.py` v0.5.0 and `verify.py` v1.0.0.

**Independent re-grade of arm U is tracked as task-7 and is NOT yet done.** Until it is, the producer's
verdicts for U are the only source, though the two arm-level counts above were re-derived by the Lead from
the raw `trial_record.json` and `verdict.json` files, not quoted from a summary.
