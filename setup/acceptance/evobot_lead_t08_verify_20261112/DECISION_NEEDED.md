# DECISION NEEDED: the T08 gripper bound cannot tell a push from a grasp

**Date** 2026-11-12 (round 53) · **Routed to a human. I will not change this myself.**

---

## The finding, stated as narrowly as the evidence allows

**Two T08 runs pushed the box correctly and were rejected on one gate.**

| run | push clause | displacement | cosine | vertical | in zone | gripper gate |
| --- | --- | --- | --- | --- | --- | --- |
| `U_shot/seed3001` | **ok = TRUE** | 144.0 mm | 0.9906 | **0.00000** | yes | **0.0035 vs bound 0.0020 → FAIL** |
| `U/seed3000` | **ok = TRUE** | 121.7 mm | 0.9976 | **0.00000** | yes | **0.0030 vs bound 0.0020 → FAIL** |

Corroborating physics from the same runs: **`max_lift` 0.39 mm** against a 20 mm allowed, **`no_attachment` 0 events**, box travelled 144 mm **along the table**.

**The run's own record says it outright** — `U/seed3000/trial_record.json` `failure_detail`:

> *"on this arm the fingers are deflected by contact, so the bound is being crossed by a push"*

A box that was **never lifted** and **never attached** is not being carried. This is finger deflection during
contact.

## Why it is a defect, not a tolerance argument

The `gripper` gate exists to separate a **push** from a **grasp-carry** — that is the whole T08 fail-closed design,
and the Master Goal demands it. Independent gate audit (F8) found the bound is **bimodal with no samples between
1.287 and 3.057**, and the 0.0020 bound sits **~154× below** the observed pass-region value. **There is no
calibrated operating point.** So the gate is not distinguishing push from grasp on this robot; it is rejecting
contact deflection.

## Scope — this is bigger than one claim

**Every T08 number this project has published depends on this gate, in both directions.**

- Runs **rejected** on `gripper` while physically pushing (≥2 found) are **false rejections** — the mission
  requires False Failure to be reported, not just False Success
- Runs **accepted** on `gripper` may be equally uncalibrated — the same bimodality cuts the other way

**The current honest state of P2 is therefore: `Simulation Tested — T08 push, 2 clean held-out instances (n=2),
zero false success`, with at least 2 further runs physically correct but failing an uncalibrated gate.**

## The three options, and what each costs

| option | what it means | my assessment |
| --- | --- | --- |
| **A. Calibrate the gripper bound** | measure aperture travel for known pushes vs known grasps on this robot, set the bound from the bimodal gap | **recommended.** It is a measurement, it would make the gate do its stated job, and it affects every T08 figure. **It is a threshold change and needs approval** |
| **B. Demote `gripper` to diagnostic** | decide push-vs-grasp from `no_lift` + `no_attachment` + `pusher_contact`, which already separate the cases cleanly in the data above | cheaper, but weakens the anti-fake design the mission specifically demanded — **I would not do this without a explicit ruling** |
| **C. Leave it** | T08 stays at n=2 with ≥2 known false rejections | honest, but the project keeps an uncalibrated gate deciding its flagship task |

## Why I am not doing any of them

All three change a **pass criterion**, and the mission forbids that without approval. **`benchmark/evaluators/evaluate.py`
is pinned**; `verify.py`'s limits are supplied by callers, but changing what value is supplied is the same act in
substance.

**I am not asking to lower a threshold to make a result look better.** The request is to *calibrate* a gate that
currently rejects correct pushes and may equally accept incorrect ones. If the calibration finds the bound is
right and these are genuine defects, that is the answer and the n=2 stands.

## What a reviewer should check before approving

1. Read `evobot_lead_t08_verify_20261112/REVIEW.md` — the independent review that produced this request.
2. Confirm the two runs above really do pass the push clause and fail only `gripper`.
3. Confirm F8's bimodality claim from the gate audit.
4. Then choose A, B, or C **and record which**, because leaving it undecided is option C by default.
