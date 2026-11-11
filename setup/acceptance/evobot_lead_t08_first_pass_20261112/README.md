# The first T08 `passed=true` — and it is the SINGLE-SHOT arm, not the recovery arm

**Date** 2026-11-12 · **Produced by** the simulation lane · **Verified by** the Lead
**Status: CONFIRMED as a pass on one dev instance. NOT a generalisation result.**

---

## 1. What happened

This is the first T08 trial in the project's history where **`passed=true`**, i.e. the terminal clause
**and** all nine evidence gates agree, from a bundle captured in the **same** run.

```
trial    S/t3
task     T08-push-seed2000  (dev instance, seed 2000)
arm      S — single-shot PushObject, ONE attempt
passed   true
terminal_passed true
evidence_status COMPLETE      physical_outcome PUSHED
failed_gates []               failed_clauses []
evaluator evaluate.py v0.5.0  verifier verify.py v1.0.0
```

**The arm matters.** `S` is the **single-shot** baseline — one `PushObject` goal, no retry, no recovery.
The closed-loop recovery arm `R` produced **0/5**. Last round's headline was that recovery improved
T08 from 2/5 to 4/5. **This batch reverses the direction.**

## 2. The numbers, per gate

| Gate | Result | Evidence |
| --- | --- | --- |
| terminal | ✅ | displacement **117.32 mm** ∈ [30, 150]; cos **0.99833** ≥ 0.9; inside zone at **18.41 mm** of 60 mm; vertical 0.0 |
| trajectory | ✅ | 6620 samples across both objects, 3310 each |
| table_support | ✅ | 0 samples off the table |
| protected_unmoved | ✅ | blue block max excursion **0.0 m** |
| no_lift | ✅ | max lift **0.102 mm** (allowed 20 mm in evidence layer) |
| pusher_contact | ✅ | 1183 motion windows, **964 overlapping** contact windows, 7 contact intervals |
| gripper | ✅ | aperture travel **0.013 mm** (limit 2 mm) — fingers did not close on anything |
| no_attachment | ✅ | 0 attachment events |
| no_teleport | ✅ | max single-step jump **1.63 mm** (threshold 30 mm) |

## 3. Independent verification performed by the Lead (not taken on trust)

I did not accept the producer's verdict. Re-derived from the raw bundle:

### 3.1 The bundle is bound to this run
```
run.run_id         t08loop-S-t3
task.task_sha256   afdeb9063fce3e72428902624fd8e8d1bbcaeb7b8df42b3947d6958232286306
task.rest_height_m 0.0175   ==   spec.objects[0].initial_pose[2] = 0.0175   (bound, not self-declared)
```

### 3.2 The trajectory is internally consistent and matches ground truth
```
target_box_a  n=3310  first xyz=(0.22000, 0.00000, 0.01750)   last xyz=(0.10288,-0.00677,0.01750)
              x span 0.11712 m, y span 0.00806 m, z 0.015769..0.017602  (max lift above rest 0.102 mm)
              sim_ns span 16.545 s, timestamps monotonic
target_box_b  n=3310  first == last == (0.20000,-0.18000,0.01750)   never moved

bundle last sample vs gt_after.json:  delta = 0.000001 m  (target_box_a)
                                      delta = 0.000000 m  (target_box_b)
```

### 3.3 The motion is in the commanded direction
```
commanded direction = (-1, 0)      measured dx = -0.11712, dy = -0.00677
|displacement| = 117.32 mm         cosine with command = 0.99833
```

### 3.4 It cannot be a carry
- **gripper** travel 0.013 mm — three orders of magnitude below the 2 mm bound, and the fingers were
  at `min=-0.000000, max=0.000013`, i.e. shut.
- **no_attachment** 0 events.
- **no_lift** max 0.102 mm above rest — the object never left the table.
- **no_teleport** max 1.63 mm per step, well under 30 mm.

**A pick-carry-place requires the object to rise. It rose 0.1 mm.** This is a genuine push.

## 4. What this does and does not establish

| Claim | Verdict |
| --- | --- |
| T08 can produce `passed=true` with a complete, same-run evidence bundle | ✅ **CONFIRMED — first time** |
| A push of 117 mm in the commanded direction actually happened in Gazebo | ✅ **CONFIRMED** from physics telemetry |
| The evidence chain (recorder → bundle → schema → 9 gates → evaluator) works end-to-end on a passing case | ✅ **CONFIRMED** — previously it had only ever been exercised on failures |
| The T08 skill is a usable capability | ❌ **NO** — see §5 |
| T08 is Independently Verified | ❌ **NO** — see §5 |
| Generalization Tested | ❌ **NO** — unseen 3000–3002 still NOT_RUN |
| Recovery improves T08 | ❌ **CONTRADICTED by this batch** — see §6 |

## 5. Why 1/5 on one dev instance is not a capability

```
arm S (single-shot):  terminal 2/5   passed 1/5
arm R (recovery)   :  terminal 1/5   passed 0/5      [R/t4 invalid: recorder defect]
```

- **1/5 = 20 %**, Wilson 95 % CI **[0.036, 0.624]** — the interval spans almost the whole range.
- Combined across both arms: **1/9 valid trials = 11.1 %**, Wilson95 **[0.020, 0.435]**.
- It is the **same dev instance** every previous T08 run used (seed 2000). This is not a new scene.
- The instance was **used for development**, so by the mission's own rule it cannot support a
  generalisation claim.

**Correct level: Simulation Tested (single instance, 1/5).** Not `SINGLE-INSTANCE SUCCESS` — that
label requires the instance to succeed reliably, and this one succeeds 1 time in 5.

## 6. The previous round's headline is contradicted

| Round | Claim | This batch |
| --- | --- | --- |
| previous | "closed-loop recovery passes 4/5 terminal clauses against a 2/5 single-shot baseline" | **R 0/5 passed, S 1/5 passed** |

Fisher exact on passed counts, valid trials only: **R 0/4 vs S 1/5 → p = 1.0000**. On terminal clauses:
**R 1/4 vs S 2/5 → p = 1.0000**. Neither difference is distinguishable from noise at this n.

**The honest summary is not "recovery got worse".** It is that **both arms are dominated by run-to-run
variance**, and the previous round's 4/5 was itself inside that variance — which the Lead's statistical
audit had already flagged (p = 0.5238 for 4/5 vs 2/5). This batch is consistent with that warning and
is the second independent demonstration that **n = 5 cannot order these arms**.

n per arm to detect 80 % vs 20 % at α=.05, power .80: **≈ 9.5**. The round has 5.

## 7. The remaining failure mode is unchanged and now better characterised

Across both arms this batch, **4 of 9 valid trials ended with cosine ≈ −1** — the block was driven
**backwards**. That is the same phenomenon the earlier single-shot arm showed 3/5 times. It is now the
single most reproducible physical fact about this task:

| Failure class | Count (valid trials) |
| --- | --- |
| `FAIL_DIRECTION` (cos ≈ −1, pushed backwards) | **4** |
| `FAIL_LIFT` (object came off the table, 7.2 mm) | 1 |
| `FAIL_ZONE` (176 mm, overshot past the zone) | 1 |
| `FAIL_OVERSHOOT` (152 mm signed vs 90 mm requested) | 1 |
| `GATE_GRIPPER` (terminal fine, 4.82 mm aperture travel) | 1 |
| **PASSED** | **1** |

**Mechanism remains UNKNOWN.** What is established is the *shape*: the end effector does not maintain a
stable contact face, so the block is either driven forward or flicked backwards depending on the contact
instant. That is a contact-geometry problem, and retrying — the recovery arm's entire strategy — cannot
fix it, which is consistent with R scoring 0/5.

## 8. Caveat that must travel with this result

The round's independent audit found the verifier is **not fail-closed against a fabricating producer**
(`evobot_t08_gate_audit_20261112/`). That does **not** taint S/t3, because:
- `rest_height_m` is bound to the spec (0.0175 == 0.0175), so the F1/F2 bypass is not in play;
- `max_z` was recomputed from the raw physics log and equals the value handed to the evaluator;
- the bundle's last sample matches `gt_after` to 1 µm, so it is not a replayed or shifted bundle.

**But it does mean this pass is trustworthy because the producer was honest, not because the verifier
would have caught a dishonest one.** That distinction is exactly why the v1.1.0 work matters, and it is
why this document does not upgrade T08's capability level.

## 9. Reproduce

```bash
python3 setup/acceptance/evobot_lead_t08_first_pass_20261112/verify_first_pass.py
```

Re-derives every number in §3 from the raw bundle and ground truth. No simulator, no model calls.
