# The first genuine generalisation measurement: task 2/6, skill 0/6

**Date** 2026-11-12 · **Produced by** the simulation lane with instance poses genuinely instantiated
**Verified by** the Lead from the raw artifacts · **n = 6** (3 frozen unseen instances × 2 arms)

**Status: CONFIRMED as a measurement. This is the project's first — round 1's unseen arm was void.**

---

## 0. Why this measurement did not exist before

Round 1's six "unseen" trials ran the **dev** world and were graded against unseen geometry
(offsets to 70.7 mm), because `sim_profile.profile()` hard-codes the block poses. That is fixed now
(`evobot_t08_instance_pose_20261112/`), and the smoke trial proved the world really starts where the
spec says. **Every trial below has `gt_before == spec.objects[].initial_pose` to < 1 µm.**

## 1. The results

| trial | terminal | **passed** | displacement | margin to 150 mm ceiling | skill's own verdict |
| --- | --- | --- | --- | --- | --- |
| U / seed3000 | ✅ | ❌ | 121.71 mm | +28.29 | ec=36 shove |
| U / seed3001 | ❌ | ❌ | **150.50 mm** | **−0.50 (over the ceiling)** | ec=29 lateral 21.9 mm |
| U / seed3002 | ✅ | ❌ | 46.51 mm | +103.49 | ec=36 shove |
| **U_shot / seed3000** | ✅ | **✅** | 147.14 mm | **+2.86** | ec=36 shove |
| U_shot / seed3001 | ✅ | ❌ | 144.00 mm | +6.00 | ec=36 shove |
| **U_shot / seed3002** | ✅ | **✅** | 140.99 mm | +9.01 | ec=28 contact lost at 30.6 mm |

```
terminal clause : 5 / 6
task passed     : 2 / 6   = 33 %   Wilson 95 % CI [0.097, 0.700]
skill's own contract satisfied: 0 / 6
```

## 2. The finding that matters: **both passes came from motion the skill itself rejected**

This is not a technicality. In **both** passing trials the frozen `PushObject` contract returned
`outcome = 1 (FAILED)`, and the object only reached the zone because the arm kept moving after the
skill had given up.

### 2.1 seed3000 — the shove

```
requested 0.0900 m, delivered 0.14679 m  = +63 % overshoot
error_code 36: "this is a shove, not a bounded push"
margin to the frozen 150 mm ceiling: 2.86 mm
```

### 2.2 seed3002 — the overdrive sweep, visible in the trajectory

The skill reported `ec=28 contact lost at increment 4: object moved 0.0306 m of 0.0900 m requested
while the arm kept advancing`. The block's own trajectory shows exactly what "kept advancing" means:

| time | block x | what |
| --- | --- | --- |
| 0.00 s | 0.1900 | start (== spec) |
| 5.40 s | 0.1770 | push begins |
| 6.75 s | 0.1599 | **skill's measured end: 30.6 mm, contact lost** |
| 9.45–10.80 s | 0.1596 | stationary; skill has declared FAILED |
| 12.15 s | 0.1666 | nudged back |
| **13.50 s** | **0.0494** | **second sweep: 117 mm in one sampling interval** |
| 16.20 s | 0.0497 | settles |

`push.py:222-233` deliberately commands a final target **beyond** the requested distance (the
overdrive) so that "reaching it proves the object yielded". After contact is lost the arm still
travels to that target — and on this run it swept the block a further **117 mm**.

**So the pass was produced by the overdrive sweep, not by the bounded push.** The skill's own
success criterion was never met; the task's geometric band was satisfied anyway.

## 3. What may and may not be claimed

| Claim | Verdict |
| --- | --- |
| The project now has a genuine unseen measurement | ✅ **CONFIRMED** — instances verified instantiated |
| Task-level pass rate on unseen: 2/6 = 33 % | ✅ **CONFIRMED** as an observation, Wilson95 [0.097, 0.700] |
| The push primitive works on unseen poses | ❌ **NO** — skill-level success 0/6 |
| T08 is Generalization Tested | ❌ **NO** — see §5 |
| The two passes are controlled pushes | ❌ **NO** — both are shoves/sweeps the skill rejected |
| The task criterion and the skill criterion agree | ❌ **NO** — they disagreed on **every** trial that passed |

**The two levels are not the same claim, and this batch is the clearest demonstration yet.** The
mission cares about the task ("push the red block into the marked zone") and the task genuinely
passed. But a report that reads "2/6 on unseen" without the skill-level 0/6 would be a level
inflation of exactly the kind the goal forbids.

## 4. The dominant failure has changed

Round 1's dominant failure on the dev instance was the block being flicked **backwards** (cos ≈ −1 in
4 of 9 valid trials). On these six unseen instances **that never happened**: every direction cosine
is between 0.989 and 0.998.

| failure class | unseen (n=6) | dev round 1 (n=9) |
| --- | --- | --- |
| backwards flick (cos < 0) | **0** | 4 |
| over the 150 mm ceiling | 1 (150.50 mm — by 0.5 mm) | 2 |
| gripper gate (terminal passed) | 2 | 1 |
| invalid evidence | 1 | 1 |
| passed | 2 | 1 |

**Do not conclude that unseen poses are easier.** n=6 cannot support that, the instances differ in
more than pose, and the dev arm's backwards flicks were a property of the *dev* block position
(0.22, 0.00) that none of the unseen instances share. What is established: the flick is
**pose-dependent**, which independently corroborates the round-2 finding that it is a contact-geometry
effect and not a property of the arm.

## 5. Why this still does not reach Generalization Tested

The ladder requires the skill to work, on frozen unseen tasks. Here:

- **skill-level success is 0/6** — the primitive never satisfied its own contract;
- the 2 task passes rest on uncontrolled dynamics, with **2.86 mm** and **9.01 mm** margins against a
  bound the same mechanism exceeded in the very next trial (150.50 mm);
- n = 6, three instances, one contact height, one arm.

**Correct level: Simulation Tested with a generalisation measurement of task 2/6, skill 0/6.**
Not Generalization Tested, and not "T08 solved".

## 6. The gripper gate is now the joint-largest failure cause

Two of the four failures are the `gripper` gate rejecting trials whose **terminal clause passed**
(U/seed3000, U_shot/seed3001). Combined with round 1's dev batch this is now a measured pattern:
**4 of 10 terminal-passing T08 trials across both batches were stopped by the aperture-travel bound
alone**, against an independently measured 22 % false-rejection rate and a limit that is untraceable
to any calibration. This raises the priority of the G1/G2/G3 calibration from "worth doing" to
**the single cheapest change that could convert real successes into recognised ones**.

## 7. Honest limits

- **n = 6.** The 95 % CI on 2/6 spans 9.7 % to 70 %. No per-instance or per-arm ordering is claimed.
- **Both arms differ only in attempt budget**, and the two passes are both from the single-shot arm —
  n = 3 per arm, so this says nothing about which strategy is better.
- The unseen instances were used **once**, after the policy was frozen (`runs/freeze.json`, git
  `3cda5cb5`, 17 hashed files). They remain unseen for future rounds **only if** no tuning follows
  from this batch. That constraint is now live.
- Everything is one dev-heights setting (0.0200). The contact-height calibration (task-9) is the
  known reason the primitive cannot do better.

## 8. Reproduce

```bash
# per-trial records, bundles, ground truth and compressed per-step logs:
setup/acceptance/evobot_t08_instance_pose_20261112/runs/
# instance-instantiation proof per trial:
setup/acceptance/evobot_t08_instance_pose_20261112/runs/*/*/t1/instance_poses.json
```
