# T08 unseen trials and gripper-aperture calibration (sim-push lane, task-8)

This directory holds the SECOND measurement round for T08, run after the instance-pose
defect was found and fixed. It contains two things that must not be read as one:

  * `U/`, `U_shot/` — six genuine unseen trials, three seeds x two arms, where the
    world now actually spawns the objects at the poses the task spec declares.
  * `calib_G1/`, `calib_G3/` — a two-run calibration of the gripper-aperture signal
    that verify.py's gripper gate decides verdicts on.

`results.tsv` is the flat table for the six trials. Everything here is reproducible from
`scripts/`.

------------------------------------------------------------------------------------------------

## 1. Read these three claims separately

The single most important thing in this directory is that the following are THREE
INDEPENDENT CLAIMS. No one of them implies another, and this round produces a case where
the first two are true and the third is false.

  (a) THE INSTANCE WAS REALLY INSTANTIATED.
      TRUE for all six. `gt_before.json`, read back from the running simulator, matches
      the task spec's declared `initial_pose` for both objects, to the digit. This is not
      an assertion about the tool; it is a measurement of the physics world.

  (b) THE FROZEN EVALUATOR PASSED THE TRIAL.
      TRUE for two of six (both single-shot): all nine evidence gates and the terminal
      clause. This says the recorded evidence is complete and consistent with the task's
      success conditions.

  (c) THE SKILL PERFORMED A CONTROLLED PUSH.
      FALSE for all six. Every push attempt in every trial returned `outcome=1` with a
      contract error code (28 contact lost, 29 off-axis, 36 overshoot). Not one trial
      delivered the requested distance within the skill's own contract.

So the task-level score is 2/6 and the skill-level score is 0/6, and BOTH numbers are
true of the same six runs. This is not a contradiction to be resolved by picking the
kinder number. It is a real disagreement between two criteria, described in section 5.

------------------------------------------------------------------------------------------------

## 2. The six unseen trials

Arm U is closed-loop with up to 3 recovery attempts. Arm U_shot is a single shot with no
recovery — the control. Task-level `passed` requires the terminal clause AND all nine
evidence gates from the same run.

| trial | arm | attempts | terminal | passed | evidence status | world disp mm | cos | zone mm | lift mm | gripper travel |
|---|---|---|---|---|---|---|---|---|---|---|
| U/seed3000      | closed loop | 1 | pass | FAIL | COMPLETE_EVIDENCE_CONTRADICTS_PUSH | 121.71 | 0.99764 | 22.99 | 1.449 | 0.003017 |
| U/seed3001      | closed loop | 1 | FAIL | FAIL | INCOMPLETE_OR_INVALID_EVIDENCE    | 150.50 | 0.98936 | 53.58 | 0.552 | 0.001940 |
| U/seed3002      | closed loop | 3 | pass | FAIL | INCOMPLETE_OR_INVALID_EVIDENCE    |  46.51 | 0.98926 | 54.42 | 2.367 | n/a (bundle invalid) |
| U_shot/seed3000 | single shot | 1 | pass | **PASS** | COMPLETE                     | 147.14 | 0.99630 | 48.28 | 0.788 | 0.000391 |
| U_shot/seed3001 | single shot | 1 | pass | FAIL | COMPLETE_EVIDENCE_CONTRADICTS_PUSH | 144.00 | 0.99064 | 46.96 | 0.389 | 0.003539 |
| U_shot/seed3002 | single shot | 1 | pass | **PASS** | COMPLETE                     | 140.99 | 0.99503 | 42.66 | 0.021 | 0.000017 |

Per-arm, from the `arm` column of `results.tsv`, which now separates them:

    U       (closed loop, 3 attempts): terminal 2/3, passed 0/3
    U_shot  (single shot, 1 attempt) : terminal 3/3, passed 2/3
    combined                         : terminal 5/6, passed 2/6

**Both passes came from the CONTROL arm.** The arm with recovery scored zero. With n=3
per arm this is not evidence that recovery hurts; it is evidence that this round produced
no evidence that recovery helps. Saying more than that would be reading noise.

### Declared versus spawned, per trial

The check this round exists to make. `logs/instance_poses_check.log` reports
`INSTANCE_POSES_OK` for each trial, and `instance_poses.json` records both sides:

| trial | A declared | A spawned | B declared | B spawned | match |
|---|---|---|---|---|---|
| U/seed3000      | (0.21,  0.03) | (0.21,  0.03) | (0.20, -0.21) | (0.20, -0.21) | yes |
| U/seed3001      | (0.23, -0.07) | (0.23, -0.07) | (0.20, -0.19) | (0.20, -0.19) | yes |
| U/seed3002      | (0.19,  0.02) | (0.19,  0.02) | (0.20, -0.23) | (0.20, -0.23) | yes |
| U_shot/seed3000 | (0.21,  0.03) | (0.21,  0.03) | (0.20, -0.21) | (0.20, -0.21) | yes |
| U_shot/seed3001 | (0.23, -0.07) | (0.23, -0.07) | (0.20, -0.19) | (0.20, -0.19) | yes |
| U_shot/seed3002 | (0.19,  0.02) | (0.19,  0.02) | (0.20, -0.23) | (0.20, -0.23) | yes |

The protected object `target_box_b` moved **0.0000 mm in all six trials**. In round 1 it
appeared to move by 10-50 mm in several trials; that was the spec-declared start compared
against the world's actual end while the two disagreed about where the block began, not
motion. With instantiation fixed, the measured motion is zero, which is what a correctly
instantiated, untouched protected object should show.

------------------------------------------------------------------------------------------------

## 3. INVALID_INFRA: U/seed3002

`U/seed3002` is labelled **INVALID_INFRA**, not failed and not deleted. The bundle is kept
verbatim. Its terminal clause passes (46.51 mm, cos 0.98926, zone 54.42 mm, lift 2.367 mm
— all inside bounds) but `schema.py` rejects the bundle with
`contacts.intervals[11]: empty or inverted interval`, so the nine gates cannot be
evaluated and `passed` must be false.

The cause is a **recorder defect, not a robot or task failure**, and it is a recurrence:
`recorder.contact_intervals()` emits a zero-length interval when contact lasts exactly one
5 ms physics step. It has now hit R/t4 [6], U/seed3000 [9,10,12], U/seed3001 [5] in round 1
and U/seed3002 [11] here. Fixing it is a change to frozen evidence tooling and was not
made.

Practical consequence: one trial whose terminal geometry succeeded is scored as not-passed
for a reason that has nothing to do with the robot. Any per-arm pass rate from this round
carries that as an unexplained-by-performance failure.

------------------------------------------------------------------------------------------------

## 4. G1 / G3: the gripper gate cannot tell a grasp from air

verify.py bounds the **total variation** of `gripper_left_joint` over the trial window at
`0.002`. It exists to separate "the gripper closed on the object, i.e. this was a
grasp/carry" from "the fingers stayed put, i.e. this was a push". Fourteen push trials were
being decided by it. It had never been calibrated.

**A unit defect, found while calibrating.** verify.py emits this quantity as
`aperture_travel_rad`, which reads as radians. It is not radians. The joint is declared
`type="prismatic"` in the URDF with limits `lower="-0.011" upper="0.02"` — the values are
**metres of finger travel**, and `0.02` is exactly the `gripper_open_position` used
throughout the configs. So the bound is 2 mm of physical finger movement, and every number
quoted in millimetres in this section is the field's value times 1000. The name is
cosmetic but "0.002 rad" would suggest a 0.11-degree rotation, which is a different
physical claim. Not renamed: verify.py is frozen.

Two runs, same world and stack as the trials (`scripts/run_gripper_calibration.sh`):

**G1 — a genuine grasp.** Descend to the block, close until the fingers stop, lift.
Verified genuine rather than assumed: the block **rose 97.4 mm**, and the contact log
records **2204 steps with finger-to-block contact**. This is a real grasp.

**G3 — closing on nothing.** Same close command in free space, then sweep the arm with no
object within reach. Verified empty: **zero** finger-to-block contacts in the whole run.

Results, on the two candidate measures:

| measure | G1 grasp | G3 air | separable? |
|---|---|---|---|
| joint travel over whole window (what the gate computes) | 31.00 mm | 24.12 mm | no — 22% apart, overlapping intent |
| GripperCommand aperture endpoints | 11.71 mm | 12.13 mm | no — 0.4 mm apart |
| **maximum object rise** | **97.9 mm** | **0 mm** | **yes — 19.6x the 5 mm bound** |

`stalled=False` and `effort=10.0` are identical in both runs: the gripper drives to its
commanded position and reports success whether or not anything is between its fingers. It
never stalls on the 35 mm block.

### This falsifies the premise verify.py is built on

verify.py's own docstring for this gate states the mechanism it relies on:

> "Grasping an object means the fingers close ON something: the aperture changes while the
> object is in hand, and **the fingers stop against the object's width**."

Measured, the fingers do not stop against the object's width. Closing on a 35 mm block ends
at `-0.001272`; closing on air ends at `-0.001692`. The difference is **0.42 mm**, and both
report `reached_goal=True`, `stalled=False`, `effort=10.0`. The commanded close is
`-0.011`, so in both cases the gripper drove essentially the whole stroke and served its
own success flag; on the block it stopped 9.7 mm short of the command but still claimed the
goal.

So the "fingers stop against the object" premise is not true of this gripper, and the gate
that depends on it is measuring drive completion, not contact. That is the mechanism behind
the weaker-signal finding below.

### The finding

**Aperture travel measures "the gripper actuated", not "the gripper held something".** It
separates a grasp from a *push* — because during a push, with the fingers never commanded,
travel is passive contact jitter and stays small (0.013 to 4.824 mm across all nine valid
dev pushes plus five valid unseen pushes). But it cannot separate a grasp from *closing on
air*, because both actuate the full stroke.

So the gate is reading the weaker of the two available signals. The strong signal is the
one already present in the bundle: did the object rise. Against the existing `no_lift`
bound of 5 mm, a genuine grasp exceeds it by ~20x while every real push in this round sits
at 0.02 to 2.37 mm — a separation of roughly two orders of magnitude, with no overlap.

Concretely: a pick-carry-place masquerading as a push leaves the block at z ≈ 0.115 m. That
is unmissable by `no_lift` and, per G1/G3, only weakly indicated by aperture travel.

The threshold itself is also mis-set. The current `0.002` (= 2 mm) sits inside the passive
range — 4 of 14 observed pushes exceed it — so it false-rejects legitimate pushes, 28.6% in
this sample. The populations are separated by a gap between 4.824 mm and 11.706 mm; a bound
placed inside that gap would clear all four false rejections, two of which were
terminal-passing this round, while still rejecting a real grasp.

**No threshold was changed.** Both corrections need human approval; this section measures
and does not act.

------------------------------------------------------------------------------------------------

## 5. The task criterion and the skill criterion disagree

Worth stating plainly because it will otherwise be read as an error:

* `error_code=36` means the skill was asked to deliver 90.0 mm and delivered 146.2 mm. The
  skill's contract requires the delivered distance to match the request within 5 mm. It is
  a **bounded-push** contract and it is STRICTER than the task.
* The task asks only that the block end 30-150 mm away, moving away from the robot, within
  the zone, without being lifted. 146.2 mm satisfies the task.

So a trial can pass the task while the skill honestly reports failure, and both statements
are correct. Treating "the skill reported FAILED" as "the task failed" would be wrong.
Equally, treating "the task passed" as "the skill performed a controlled push" would be
wrong — and that is exactly what happened in the two passing trials:
`U_shot/seed3000` passed with only **2.86 mm** of margin to the 150 mm ceiling while
overshooting its request by 63%. `U_shot/seed3002` is stranger still: the skill lost
contact at increment 4 and its last measurement reads 30.6 mm of a 90 mm request, but the
block's final pose is 141 mm from its start. The physics trace shows why — the block came
to rest at x = 0.1596, then was struck again later in the window and travelled on to
x = 0.0497, partly under a further contact event and partly coasting. So the skill's own
displacement report **understates** what happened to the block, by 110 mm, and the
evaluator graded `gt_after` rather than the skill's number, which is the correct choice.

Neither pass is evidence of a controlled push. Both are evidence that a shove can land
inside the task's acceptance window.

------------------------------------------------------------------------------------------------

## 6. Scope of the round-1 instantiation defect (corrected)

Measured against every task spec in `benchmark/tasks/`, comparing each spec's declared
`initial_pose` to the pose `sim_profile.profile()` hard-codes:

    t08_dev     n=3   affected=2   (seed2001, seed2002)
    t08_unseen  n=3   affected=3   (all three)
    train       n=72  affected=0
    val         n=36  affected=0

train and val are clean because they vary the ZONE, which `sim_profile` does accept; only
the object poses were hard-coded. So **the earlier held-out/public result is not
contaminated**, and the corrected statement is "5 specs", not "the whole benchmark".

`T08-push-seed2000` matches the hard-coded world exactly, which is why the round-1 dev
results (R and S arms, n=9 valid) remain valid and are still cited.

------------------------------------------------------------------------------------------------

## 7. Freeze status: one drift, disclosed

The pre-run fingerprint in `freeze.json` (git HEAD `3cda5cb5`) does **not** verify clean
at the end of this round. `inject_instance_poses.py` and its test changed mid-batch, at
03:31:49, when the zone-marker fix was committed as `59a9d7f5` — after five of the six
unseen trials had already run.

Exactly which trials used which version, from the world-file timestamps:

    U_shot/seed3000  03:27:35  pre-change
    U/seed3000       03:29:25  pre-change
    U/seed3001       03:29:59  pre-change
    U/seed3002       03:30:31  pre-change
    U_shot/seed3001  03:31:23  pre-change
    U_shot/seed3002  03:31:56  POST-change
    calib_G1, calib_G3        POST-change

**Why this cannot have changed a verdict.** Verified rather than argued:

* The object-writing code path is **byte-identical** across the change: the spec-objects
  loop (828 bytes) compares equal, and `set_model_pose`, `read_model_pose` and
  `_finite_triple` hash identically by AST. The change only appends zone-marker handling
  after the object loop.
* Zone markers are `<static>true</static>` with **no collision geometry** — confirmed in
  every generated world. They are paint on the table; they cannot touch the arm or the
  block.
* Independently of the tool, each trial's `gt_before.json` was read back from the running
  simulator and matches its spec. The per-trial evidence therefore does not depend on
  trusting the injector at all.

The drift is still a drift: the fingerprint is broken and a re-run would use the later
commit. It is recorded here rather than quietly re-frozen.

One visible consequence, disclosed rather than smoothed over: `U_shot/seed3002` is the
only trial whose world carries the corrected zone markers (`zone_1` at the spec's
(0.09, 0.02)); the other five still show the hard-coded `zone_1` at (0.12, -0.15) and
`zone_2` at (0.25, 0.05). So within this one table, the visual marker and the graded zone
agree for one trial and disagree for five. Because the markers carry no collision geometry
and grading reads the spec, this changes no number — but a reader comparing screenshots
across these six trials would be looking at two different tables.

------------------------------------------------------------------------------------------------

## 8. Two defects in the first version of results.tsv, and their fixes

Both were caught by the Lead reading the committed table. Both would have misled a reader
who trusted one column pair, which is the same failure class as round 1's mixed-window
displacement errors.

**(i) The `arm` column did not separate the arms.** The trial record's `arm` field is the
nested census path (`"U/seed3000"`), so an equality test against `"U"` was false for every
recovery row and every row printed as single-shot. Any per-arm count from that column
would have been wrong. Fixed: the column now splits on the top-level arm and reads
`U (closed loop, 3 attempts)` / `U_shot (single shot, 1 attempt)`.

**(ii) Two columns came from different windows in one row.** On `U_shot/seed3002`,
`displacement_signed_mm` was 30.446 (that attempt's own measured slots) while
`direction_cos` was 0.99503 (the bundle's start-to-end displacement). Dividing one by the
other gives an impossible cosine. Both numbers are real measurements of different events:
the skill lost contact having moved the block 30.6 mm, and the block then slid to 141 mm.
Fixed: the table now has explicitly separated blocks —
`world_*` (bundle start to end, what evaluate.py grades) and
`skill_last_attempt_*` (that attempt's own slots) — and no column pair from the two
should be combined.

Neither defect changed a verdict; both were recomputable from `trial_record.json` and the
bundles.

------------------------------------------------------------------------------------------------

## 9. Mechanical honesty statement

* No threshold, limit or frozen file was changed in this round. `contracts/push.py`,
  `push_recover.py`, `push_server.py`, `evaluate.py` v0.5.0, `recorder.py`,
  `verify.py`, `schema.py`, `sim_profile.py` and `benchmark/tasks/**` are untouched.
* All bundles are verbatim. Nothing was hand-patched. The invalid bundle was kept and
  labelled, not repaired.
* Nothing was committed to git by this lane.
* Three Gazebo runs were spent on G1+G3 rather than two: the first G1 attempt reused
  pick_server's declared grasp target, which sits 160 mm above the block because that stack
  "grasps" by magnetic carry from a distance. It recorded zero finger contact and a
  0.000000 m rise. That failed attempt is described in the script's comments so the
  wrong choice is not repeated; its directory was overwritten by the corrected run.
* Trials were not re-run for unwelcome results. Re-runs were for a broken grasp target and
  the INVALID_INFRA labelling, never for an outcome.

## 10. Files

    results.tsv                     the six trials, 23 columns, windows separated
    U/<seed>/t1/                    U arm: evidence bundle, verdict, push/recovery records
    U_shot/<seed>/t1/               U_shot arm: same
    calib_G1/, calib_G3/            gripper calibration runs, with logs
    scripts/gripper_calibration.py    the G1/G3 driver
    scripts/run_gripper_calibration.sh  one world per mode, lock-guarded
    logs/instance_poses_check.log   INSTANCE_POSES_OK per trial
    logs/contact_steps.jsonl        per-step contact trace
    logs/physics_steps.jsonl        per-step object poses
