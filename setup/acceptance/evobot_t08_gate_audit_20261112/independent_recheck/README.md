# Independent re-derivation of the T08 evidence-loop verdicts (task-3)

**Auditor** gate-auditor (independent validation lane) · **Date** 2026-11-12  
**Inputs** `setup/acceptance/evobot_t08_evidence_loop_20261112/evidence/`  
**Method** my own `evaluate.evaluate()` invocation; producer's `verdict.json` never
used as the verdict  
**Scope at time of writing** arms R (5/5) and S (5/5) complete; arm U not yet run

---

## 1. Verdict: the producer's verdicts are HONEST

**10 trials re-graded, 0 disagreements, FALSE_SUCCESS = 0, FALSE_FAILURE = 0.**

| trial | producer passed | my passed | agree | failed gates (both agree) |
| --- | --- | --- | --- | --- |
| R/t1 | false | false | ✓ | `gripper` |
| R/t2 | false | false | ✓ | `terminal` (cos = −0.99269, pushed the wrong way) |
| R/t3 | false | false | ✓ | `terminal` (max_lift 7.2 mm vs 0.005) |
| R/t4 | false | false | ✓ | all nine (incomplete artifact set) |
| R/t5 | false | false | ✓ | `terminal` |
| S/t1 | false | false | ✓ | `terminal` |
| S/t2 | false | false | ✓ | `terminal` |
| **S/t3** | **true** | **true** | ✓ | **none — all nine gates pass** |
| S/t4 | false | false | ✓ | `gripper` |
| S/t5 | false | false | ✓ | `terminal` |

Machine-readable: `recheck.tsv`, per-trial detail in `verdicts/`.

## 2. The producer's claimed fixes are REAL (verified, not assumed)

The sim lane stated it had bound `rest_height` to the spec and recomputed `max_z`
independently. I checked both against the artifacts rather than the claim:

| claim | how I checked | result |
| --- | --- | --- |
| `rest_height` bound to spec | compared `bundle.task.rest_height_m` to `spec.objects[target].initial_pose[2]` for every trial | **0.0175 == 0.0175 on all 10** |
| `max_z` recomputed from the raw log | recomputed max z myself from `logs/physics_steps.jsonl` and compared to `evaluator_input.trajectory.max_z_m` | **identical on all 10** (e.g. S/t3: 0.0176016846 vs 0.017601685) |
| bundle digest binds to bytes | recomputed the file sha256 and compared to `trial_record.bundle_sha256` | **matches on all 10** |
| task identity | recomputed the spec file sha256 and compared to `bundle.task.task_sha256` | **matches on all 10** |

The `source` tag on the recomputed value is literally `RECOMPUTED_FROM_PHYSICS_LOG`,
and the number agrees with the log. **The F1/F2 fabrication bypass is not being
exercised by this batch** — the producer reports what the recorder measured.

## 3. The one passing trial (S/t3) — attacked, and it holds

`S/t3` is the round's only `passed=true`. Because a single pass is the most valuable
thing to fake, I attacked it with every bypass found in the gate audit:

| attack | result |
| --- | --- |
| is `rest_height` fabricated? | no — 0.0175, equals spec |
| is `max_z` fabricated? | no — recomputed from 3310 physics rows, matches |
| gripper vacuity (n=1 span)? | no — n=1596, travel 0.013 mm |
| pusher self-declared? | no — both real gripper links, 7 overlapping contact intervals |
| teleport declared vs measured | 0.001632 vs 0.001632 — agree |
| attachment / dropped samples | events 0, dropped 0/0 |
| window contains samples | 5 ms .. 16.55 s covers 5 ms .. 16.55 s |
| ends in zone? | final (0.1029, −0.0068) vs centre (0.12, 0.0) r=0.06 → **18.4 mm, inside** |
| protected object moved? | max excursion **0.000000 m** |
| terminal geometry | displacement 117.32 mm ∈ [30,150], cos 0.99833, lift 0.0001 m |

**It also passes under `verify.py` v1.1.0**, which is strictly stricter (binds rest to
spec, recomputes the digest, requires a run binding, checks manifest completeness,
refuses n<2 gripper spans, allow-lists pusher links). Divergence between v1.0.0 and
v1.1.0 across all 10 trials: **0**.

**S/t3 is a genuine push.** Not a carry, not a replay, not a fabricated bundle.

## 4. The gripper gate's real distribution (n=10, first time available)

The gate bounds aperture **travel** (metres; the joints are prismatic). With the full
batch there is finally a distribution:

| trial | n | travel | vs 2 mm |
| --- | --- | --- | --- |
| S/t3 | 1596 | 0.013 mm | ok — **the passing trial is 154x under the limit** |
| R/t2 | 1586 | 0.132 mm | ok |
| S/t2 | 1542 | 0.234 mm | ok |
| S/t1 | 1569 | 0.970 mm | ok |
| R/t5 | 1580 | 1.037 mm | ok |
| R/t3 | 2067 | 1.287 mm | ok |
| **R/t1** | 1666 | **3.057 mm** | FAIL (1.53x) |
| **S/t4** | 1563 | **4.824 mm** | FAIL (2.41x) |
| R/t4 | 2642 | 6.518 mm | FAIL (3.26x) |

Two of ten non-grasp pushes exceed the 2 mm bound, and the one genuine pass sits
154x **below** it. This sharpens F18: the bound does not merely fail to separate
grasp from contact — it rejects ordinary non-grasping pushes at a ~20% rate while
passing the one run everyone agrees is a clean push by a factor of 154.

**This is a false-rejection rate, not a false-accept.** It lowers measured capability;
it cannot manufacture a success. The correct response is the G1/G2/G3 calibration
experiment in `FINDING_F18_GRIPPER_CORRECTION.md` §4 — **not** raising the number.

## 5. What I could not verify

| item | status |
| --- | --- |
| arm U (unseen seeds 3000/3001/3002) | **NOT RUN** at time of writing — no artifacts exist |
| S/t4, S/t5 early snapshots | were BLOCKED mid-batch (artifacts still being written); re-graded successfully once complete |
| `R/t4` | evidence bundle present but trial failed at the terminal layer and all nine gates failed as unevaluable — reported as produced, not filled in |

No trial was left unexplained and no gap was filled.

## 6. Bearing on the round's headline

The recovery arm R did **not** produce a pass (0/5). The single-shot arm S produced
**1/5** (S/t3). Both are far below any capability claim, and the honest summary is that
the closed-loop recovery policy did not beat single-shot on this batch — the opposite
of the direction the round was hoping to establish.

**S/t3 is the only T08 `passed=true` produced this round, and it is trustworthy** — but
it is a single trial from the *control* arm, not the recovery arm, and it must not be
reported as evidence that recovery works.
