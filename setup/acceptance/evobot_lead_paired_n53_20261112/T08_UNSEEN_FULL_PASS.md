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
