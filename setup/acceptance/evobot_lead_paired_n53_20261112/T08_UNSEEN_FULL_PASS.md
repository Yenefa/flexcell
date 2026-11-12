# T08 full pass on unseen seed 3000 — all nine anti-fake gates satisfied

**Date** 2026-11-12 (round 46) · **The strongest capability evidence in this session.**

`setup/acceptance/evobot_t08_instance_pose_20261112/runs/U_shot/seed3000/t1/verdict.json`

```
terminal_passed : True        passed : True
evidence_status : COMPLETE
false_success   : False       agent_claimed_success : False
```

## The nine gates — every one `ok: true`

| gate | evidence |
| --- | --- |
| terminal | passed |
| **trajectory** | **6680 samples**, objects `[target_box_a, target_box_b]` |
| table_support | **0** off-table samples (tol 0.01 m) |
| protected_unmoved | max excursion **0.0 m** (tol 0.005) |
| **no_lift** | max lift **0.000788 m** against an allowed 0.02 — **the box was not raised** |
| **pusher_contact** | **1176 of 1182 motion windows overlapping**, 10 contact intervals, pusher links `gripper_left_link_collision` / `gripper_right_link_collision` |
| gripper | aperture travel **0.000391 rad** vs limit 0.002 — **the gripper did not open or close meaningfully** |
| **no_attachment** | **0 events** |
| no_teleport | max jump **0.000561 m** vs threshold 0.03 |

## Why this is the finding that matters

**These are precisely the gates that make T08 unfakeable by pick-carry-place**, which is what the Master Goal
demanded:

- `no_lift` + `no_attachment` + gripper-aperture-stability prove the box was **not grasped**
- `pusher_contact` proves the **gripper links actually contacted** the box across 1176 motion windows
- `table_support` + `no_teleport` prove the motion was **physically continuous** on the table
- `trajectory` with 6680 samples is the evidence the clause fails closed without — **the thing my own harness never supplied**

**A pass with all nine gates satisfied cannot have been achieved by carrying the box.** That is exactly the
property P2 was built to enforce, and here it is enforced and passed.

## Evidence level, stated without inflation

| claim | level |
| --- | --- |
| T08 full pass with all nine fail-closed gates, on an **unseen** seed | **Independently Verified** (machine-gated from trajectory; not self-reported) |
| same on seeds **3001** and **3002** (`U_shot`) and seeds **3000**, **3002** (`U`, closed-loop) | **same, from the verdict scan** |
| number of distinct **unseen instances**: **3** | **this is small** |
| **Generalization Tested** | **reached in kind, thin in n** — three unseen instances is not a generalization study, and I will not call it one |

## What this corrects, finally

For twenty rounds I reported that this arm could not perform T08. It performs it, on unseen geometry, with the
anti-fake gates all green, **without needing the retry strategy** (`U_shot` is single-shot).

The archive held this the entire time. I was reading a graded number from my own starved harness instead.

## What remains unverified

1. **`U_shot` means single-shot** — inferred from `run_batch_v2.sh:278`, not from a manifest. If it means
   something else, the "without retries" part of this claim weakens (the gates themselves stand regardless).
2. **The three seeds are 3, not more.** No claim beyond "three unseen instances passed with full gating".
3. I have **not** re-run anything. Every number above is read from committed artifacts.
---

## Confirmation (round 47): `U_shot` is single-shot, from the trial record — not from naming

The one thing marked unverified above is now verified from the artifact that records it:

`runs/U_shot/seed3000/t1/logs/evidence.log`

```json
TRIAL_RECORD {
  "arm": "U_shot/seed3000",
  "attempts": 1,                       <-- SINGLE ATTEMPT, confirmed
  "attempt_error_codes": [36],
  "bundle_component_present": true,
  "bundle_contact_intervals": 10,
  "bundle_problems": [],
  "clause_ok": true,
  "contact_height_m": 0.02,
  "contact_rows": 3344,
  "contact_trace_in_world": true,
  "direction_cos": 0.9963,
  "displacement_mm": 147.14,
  "dist_to_zone_mm": 48.28,
  "evidence_status": "COMPLETE",
  "failed_clauses": [],
  "failed_gates": [],
  "failure_category": null
}
```

**`attempts: 1`.** No retry. The task was completed on the first push, on an unseen instance.

## What the numbers say, read against the frozen bounds

| quantity | value | bound | verdict |
| --- | --- | --- | --- |
| attempts | **1** | — | **single shot** |
| displacement | **147.14 mm** | [30, 150] | inside, **2.86 mm under the ceiling** |
| direction cosine | **0.9963** | ≥ 0.90 | passes |
| distance to zone | **48.28 mm** | ≤ 60 | passes |
| evidence status | **COMPLETE** | required | passes |
| failed clauses / gates | **[] / []** | empty | passes |

**Note `attempt_error_codes: [36]`** — `ERR_DISPLACEMENT_OVERSHOOT`. The skill flagged its *own* push as an
overshoot; the evaluator graded the outcome and it was inside the bound at 147.14 mm. **The skill was
conservative about itself and the final state was correct.** That is worth recording: it is the opposite of a
false success claim.

## The claim, at the level the evidence supports

| claim | level |
| --- | --- |
| **T08 completed on an unseen instance in a single push**, all nine anti-fake gates satisfied, evidence COMPLETE | **Generalization Tested — single instance confirmed directly; two further seeds (3001, 3002) pass by the same gate pattern** |
| quantity of generalization evidence | **3 unseen instances** — thin |
| false success on this trial | **none** — `agent_claimed_success: false`, `false_success: false`, and the skill actually reported its own error |

**I am calling this Generalization Tested for T08, and stating immediately that n=3 is thin.** The distinction I
am drawing: the *quality* of the evidence is high — nine independent physical gates over a 6680-sample
trajectory, plus a separately recorded trial record showing `attempts: 1` — while the *breadth* is three
instances. A generalization study needs more. **A generalization claim of "it has been done on three unseen
instances with full gating" is exactly what the artifacts support, and no more.**

## The final correction to my own record

Round 17 said the arm could not do T08 and I treated that as settled for twenty rounds. **It was wrong in a way
that a single filed read would have caught.** The archive contains a single-push, fully-gated, evidence-complete
T08 success on unseen geometry, and it was recorded before I started.
---

## Correction (round 49): only TWO of the six have `evidence_status: COMPLETE` — n=2, not 3

I checked every U/U_shot trial record rather than trusting the verdict scan. The verdict flag `passed: true` is
**not** the same as valid evidence, and this is exactly where the difference bites.

| trial | attempts | clause_ok | evidence_status | displacement | valid? |
| --- | --- | --- | --- | --- | --- |
| `U_shot/seed3000` | 1 | True | **COMPLETE** | 147.14 | **YES** |
| `U_shot/seed3002` | 1 | True | **COMPLETE** | 140.99 | **YES** |
| `U_shot/seed3001` | 1 | True | COMPLETE_EVIDENCE_CONTRADICTS_PUSH | 144.00 | **NO** |
| `U/seed3000` | 1 | True | COMPLETE_EVIDENCE_CONTRADICTS_PUSH | 121.71 | **NO** |
| `U/seed3002` | 3 | True | INCOMPLETE_OR_INVALID_EVIDENCE | 46.51 | **NO** |
| `U/seed3001` | 1 | False | INCOMPLETE_OR_INVALID_EVIDENCE | 150.50 | no (clause failed) |

## What changes

| claim | before (round 47) | now |
| --- | --- | --- |
| valid unseen full passes | "3 seeds, plus closed-loop 3000 and 3002" | **2: `U_shot/seed3000` and `U_shot/seed3002`** |
| level | Generalization Tested, thin | **Generalization Tested, thinner — n=2** |
| `U` (closed-loop) runs | "same gate pattern" | **neither is valid** — one contradicts, one incomplete |

**`COMPLETE_EVIDENCE_CONTRADICTS_PUSH` is not a pass.** Whatever it means precisely, it is the evaluator
reporting that the evidence conflicts with the push claim, and treating it as a pass because a separate flag said
`passed: true` would be precisely the error this session keeps repeating — **trusting a summary flag over the
artifact that qualifies it.**

## The claim that survives, stated at its true width

**T08 is Generalization Tested at n = 2**: two unseen instances (`seed3000`, `seed3002`), each completed in a
**single attempt**, each with `evidence_status: COMPLETE` and all nine anti-fake gates satisfied, zero false
success, and on `seed3000` verified in full detail (6680 trajectory samples, `no_lift` 0.000788 m,
`no_attachment` 0 events, `pusher_contact` 1176/1182 windows).

**Two instances is not a generalization study.** It is two instances. The mechanism is demonstrated and the
evidence quality is high; the breadth is two.

## What I got wrong forty minutes ago

Round 47 said "two further seeds pass by the same gate pattern". **That was inferred from the verdict scan's
`passed: true`, which I had explicitly warned in round 44 was not sufficient — and then used anyway.** The
correct check was one file per trial, which took one command.
