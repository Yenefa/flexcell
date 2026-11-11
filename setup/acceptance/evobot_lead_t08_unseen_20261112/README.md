# RETRACTED: the unseen arm did not run the unseen instances

**Date** 2026-11-12 · **Status: RETRACTED IN FULL by the Lead, on the simulation lane's evidence.**
**This file replaces an earlier version that claimed "0/6 unseen". That claim was WRONG.**

---

## 1. What was claimed, and why it was wrong

The earlier version of this document reported that T08 failed on all six unseen trials and called
that "the first generalisation measurement, and it is negative". **That is retracted.**

The six trials **never instantiated the unseen task geometry.** `sim_profile.py` hard-codes the spawn
poses for the benchmark blocks and takes no per-instance pose argument:

```
target_box_a  ->  <pose>0.220000  0.000000 0.0175</pose>     (seed-2000 dev geometry)
target_box_b  ->  <pose>0.200000 -0.180000 0.0175</pose>     (seed-2000 dev geometry)
```

Verified in every one of the six `sim/world.sdf` files, for both arms and all three seeds: the spawn
poses are **identical** across all six, and they match the **dev** spec, not any unseen spec.
`sim_profile.profile()` accepts `zone_2_pose` but **no box-pose argument**, so no supported path in this
pipeline can place a task's objects where its spec says they are.

**So what ran was the dev world six more times, graded against unseen geometry.**

## 2. The measured consequence

Spec-declared start vs actual world spawn:

| Seed | Object | Spec XY | World XY | Offset |
| --- | --- | --- | --- | --- |
| 3000 | `target_box_a` | (0.21, 0.03) | (0.22, 0.00) | **31.6 mm** |
| 3000 | `target_box_b` | (0.20, −0.21) | (0.20, −0.18) | **30.0 mm** |
| 3001 | `target_box_a` | (0.23, −0.07) | (0.22, 0.00) | **70.7 mm** |
| 3001 | `target_box_b` | (0.20, −0.19) | (0.20, −0.18) | 10.0 mm |
| 3002 | `target_box_a` | (0.19, 0.02) | (0.22, 0.00) | **36.1 mm** |
| 3002 | `target_box_b` | (0.20, −0.23) | (0.20, −0.18) | **50.0 mm** |

## 3. A second error of mine, in the same document

The retracted version said the `unmoved` clause failures were **real robot failures** because
"the blue block moved 0.030 / 0.010 / 0.050 m". **That is wrong too.** Re-derived from ground truth:

```
U       seed3000..3002   target_box_b world motion = 0.000000 m   (all three)
U_shot  seed3000..3002   target_box_b world motion = 0.000000 m   (all three)
```

**The blue block never moved in any unseen trial.** The clause's `distance_m` of 0.030 / 0.010 / 0.050 m
is exactly the **spec-vs-world spawn offset**, not motion. I read the clause's distance field as if it
were a displacement between two world states, when it is a distance between the spec's declared start
and the world's actual end — and the world started somewhere else.

This is the same class of error I spent the round finding in others' work: **reading a number without
checking what it is a number *of*.**

## 4. The push displacements were also distorted, in both directions

Recomputed on the world basis (ground truth before → after):

| Trial | Evaluator read | Actual world motion | Consequence |
| --- | --- | --- | --- |
| U/seed3000 | 147.45 mm (under the 150 ceiling) | **155.32 mm** | would be **OVER** the ceiling |
| U/seed3001 | 166.21 mm | 158.63 mm | over either way |
| U/seed3002 | 118.05 mm | **145.19 mm** | different margin entirely |
| U_shot/seed3000 | 45.79 mm | **29.50 mm** | would be **UNDER** the 30 mm floor |
| U_shot/seed3001 | 76.41 mm | **33.14 mm** | near the floor |
| U_shot/seed3002 | 54.82 mm | **19.85 mm** | would be **UNDER** the floor |

**So the six trials cannot even be scored against the unseen clauses**, because the grader's frame and
the world's frame differ by up to 71 mm on a task whose whole tolerance band is 30–150 mm.

## 5. Verdict

| Item | State |
| --- | --- |
| The six unseen trials | **INVALID_INFRA (Environment)** — not measurements of the unseen tasks |
| "0/6 on unseen" | **RETRACTED — never measured** |
| "T08 fails to generalise" | **WITHDRAWN** — no generalisation measurement exists |
| T08 unseen 3000–3002 | **NOT_RUN**, and the harness cannot currently run them |
| Arms R and S (dev) | **UNAFFECTED** — seed-2000 spec matches the world exactly (delta 0.000 m), verified on R/t1 and S/t3 |
| S/t3 `passed=true` | **UNAFFECTED and still valid** |
| 9-valid-dev-trial failure-class counts | **UNAFFECTED** |

## 6. What this means for the round

**The round has NO generalisation result.** That is different from, and less bad than, "generalisation
failed" — but it is also less than was claimed an hour ago.

The honest statement is: **T08 produced one verified pass on one dev instance (1/9 valid dev trials),
and generalisation is UNMEASURED because the harness cannot instantiate a task's declared initial poses.**

## 7. The blocker this exposes is bigger than the arm

**No task in this benchmark has ever been instantiated at its declared initial pose**, except where the
spec happens to coincide with the hard-coded world (the dev spec does). That means:

- every "unseen" or "held-out" measurement attempted through this pipeline would be void;
- `benchmark/tasks/val/` and any regenerated specs with different poses are equally uninstantiable;
- the held-out generalisation result reported in earlier rounds (`evobot_heldout_n6_20261111/`) needs
  its initial poses re-checked against this defect before it is quoted again. **That check has NOT been
  done** and is the highest-priority verification for the next round.

**Fix required (outside the sim lane's scope, needs a decision):** either a per-instance world generator
that reads `spec.objects[].initial_pose`, or a supported `set_pose` path after spawn for the T08 push
task. `PushObject` has no initial-pose field, so this is a harness change, not a driver flag.

## 8. Credit

The simulation lane found this, verified it three ways (world.sdf poses, spec-vs-world offsets, ground
truth motion), reported it **before** publishing a result it could have kept, and refused to rerun or
tune. It also corrected two claims of mine in the process. This document exists because they did not
let a wrong headline stand.

## 9. Reproduce

```bash
python3 setup/acceptance/evobot_lead_t08_unseen_20261112/check_world_poses.py
```

Reads the six `world.sdf` files, the unseen specs, and `gt_before`/`gt_after`. No simulator, no model calls.
