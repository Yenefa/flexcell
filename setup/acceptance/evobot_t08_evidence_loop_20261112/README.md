# T08 evidence-complete closed-loop push — one driver, one world, full bundle

**Date** 2026-11-12 · **Lane** sim-push (sole Gazebo owner this round) · **Branch** `autonomous/flexcell-remediation`
**Pre-U HEAD** `a6fe30afe00f11fe0f2cd08b47412ab274ec98ca` · **16 real Gazebo runs** · **0 LLM calls** · **0 orphans after every trial**

---

## 0. READ THIS FIRST — the benchmark has never instantiated a task's declared initial poses

This is the most important thing in this batch, and it is bigger than the arm it was found in.

Every T08 trial in this batch — and, as far as this lane can tell, every T08 trial in the
project's history — ran a world in which `target_box_a` is spawned at **(0.220, 0.000)** and
`target_box_b` at **(0.200, -0.180)**, regardless of what the task JSON declares. Those two poses
are hard-coded in `flexcell_velocity_servo.sdf`, and `sim_profile.profile()` (`sim_profile.py:55`)
takes **no object-pose argument**. Nothing in the pipeline reads
`spec.objects[].initial_pose` to place anything: `generate_t08.py` only *writes* that field,
`evaluate.py` only *reads* it to grade.

Consequence: a task instance is only genuinely instantiated where its declared poses
happen to coincide with the hard-coded world. **The dev instance `T08-push-seed2000` does
coincide exactly** (delta 0.000 m). Every unseen instance (3000/3001/3002) does **not**.

Measured, from the `gt_before.json` of each trial and the `sim/world.sdf` that actually ran
(`scripts/audit_geometry.py` reproduces every number):

| instance | declared A | world spawns A | declared B | world spawns B | largest offset |
| --- | --- | --- | --- | --- | --- |
| seed2000 (dev) | (0.22, 0.00) | (0.22, 0.00) | (0.20, -0.18) | (0.20, -0.18) | **0.00 mm** |
| seed3000 | (0.21, 0.03) | (0.22, 0.00) | (0.20, -0.21) | (0.20, -0.18) | **31.62 mm** |
| seed3001 | (0.23, -0.07) | (0.22, 0.00) | (0.20, -0.19) | (0.20, -0.18) | **70.71 mm** |
| seed3002 | (0.19, 0.02) | (0.22, 0.00) | (0.20, -0.23) | (0.20, -0.18) | **50.00 mm** |

**All six unseen trials are INVALID_INFRA (Environment).** They are not passes, not failures,
and not measurements of the unseen instances — the instances were never set up. This batch
therefore supplies **no generalisation measurement**, and nothing here may be quoted as
"T08 does not transfer to unseen poses".

Two further facts make the misclassification concrete rather than theoretical:

* The blue block **never moved** in any of the six unseen trials: world-basis motion
  `0.000000 m` in all six. The `unmoved:target_box_b` clause failed purely on the spawn offset
  (e.g. `distance_m` 0.03000 == the B offset 0.030000). A clause graded against a pose the
  object never occupied cannot testify about the robot.
* The reported displacement is measured from the **declared** start, not the actual one, so it
  is wrong in both directions:

| instance | evaluator read | actual world-basis motion | frozen bound crossed |
| --- | --- | --- | --- |
| U seed3000 | 147.45 mm | **155.32 mm** | over the 150 mm ceiling (the read said *under*) |
| U seed3001 | 166.21 mm | 158.63 mm | over ceiling |
| U seed3002 | 118.05 mm | 145.19 mm | — |
| U_shot seed3000 | 45.79 mm | **29.50 mm** | under the 30 mm floor (the read said *over*) |
| U_shot seed3001 | 76.41 mm | **33.14 mm** | near the floor |
| U_shot seed3002 | 54.82 mm | **19.85 mm** | under the 30 mm floor (the read said *over*) |

### The harness capability gap (so the next round does not rediscover it)

There is **no supported way to instantiate a T08 push task's initial object poses**:

* `PushObject.action` has no initial-pose field — it takes an object **name** and a direction.
* `sim_profile.profile()` has no box-pose argument; the target boxes are hard-coded in the world file.
* `gz set_pose` **is** wired into this stack, but only inside the carry / preposition machinery
  (`carry_server.py:93`, `pose_request_worker.py`), not as a task-setup step.
* There is no benchmark harness that reads `spec.objects[].initial_pose` and applies it.

Fixing this is a **harness change outside this lane's write scope** (it would mean a new setup
step and a decision about whether the world is generated per-instance or posed after spawn).
This batch deliberately did **not** attempt a `set_pose` workaround: doing so would have changed
the object's physical initial state mid-protocol and produced numbers that look like a
measurement while resting on an untested setup step.

**Knock-on for earlier rounds:** `setup/acceptance/evobot_heldout_n6_20261111/` and any other run
whose specs differ from the hard-coded world need their initial poses re-checked against this
defect before being quoted. That check is **NOT_RUN** here and its status is **UNKNOWN**.

---

## 1. What this batch was for, and what it actually delivered

The round wanted a **decidable** T08 result: previous rounds produced either a terminal verdict
(geometry only) or an evidence bundle (physics only), in **separate runs**. Joining two
separate runs proves nothing about the same physical event, so `evaluate.py` v0.5.0 — which
requires terminal clauses **and** nine physical gates from the **same** run — could never emit
`passed=true`.

This batch runs **one driver** that executes the push policy **and** captures the complete
evidence bundle in the **same world**, then feeds
`{objects: gt_after, trajectory, evidence: bundle}` to the frozen evaluator. Result: **the first
`passed=true` in the project's history** — and it came from the **control arm**, which matters (`5).

---

## 2. The four states, kept separate

Per the mission's discipline, these are four different things and are never collapsed:

| state | how it is established here | result |
| --- | --- | --- |
| **planning_correct** | the driver asked for a request the frozen policy implies (`push_recover.choose_next_request`), recorded per attempt in `recovery.json` | yes in all 16 trials; the policy never asked for a non-positive or out-of-range distance |
| **execution_succeeded** | the push physically delivered motion, measured by ground truth (not by the skill's self-report) | 10 of 10 dev trials moved >= 38.65 mm; 6 of 6 unseen trials moved, but those trials are **INVALID_INFRA** for grading (`0) |
| **independent_evaluation_passed** | frozen `evaluate.py` v0.5.0, terminal clauses **and** 9 evidence gates, on the same run | **1 / 10 dev trials** (`S/t3`); **0 / 6** unseen valid-but-void |
| **agent_claimed_success** | this batch never claims success. `agent_claimed_success` is passed to the evaluator as `false` | **false in all 16**; `false_success` = false in all 16 |

The distinction that matters most: **"we could not measure" != "we measured and it failed."**
Six trials in this batch fall in the first bucket (Environment), one falls in a third bucket
(Tooling, `R/t4`), and nine are genuine measurements of the dev instance.

---

## 3. Arms R and S are UNAFFECTED by `0, and here is the proof

`T08-push-seed2000` declares `A=(0.22, 0.00)`, `B=(0.20, -0.18)` — **byte-identical to what the
hard-coded world spawns**. Verified on `R/t1` and `S/t3`:

```
$ python3 scripts/audit_geometry.py
R       t1           2000   0.00         149.07       149.07       YES
...
S       t3           2000   0.00         117.32       117.32       YES
U       seed3000/t1  3000   31.62        147.45       155.32       NO - INVALID_INFRA
```

So the dev table, the failure-class counts over 9 valid dev trials, and `S/t3`'s `passed=true`
stand on their own. Only the unseen arm is void.

---

## 4. Dev arm results — `T08-push-seed2000`, `contact_height_m = 0.0200`, n = 5 per arm

Both arms, same world, same height, same evaluator. R = closed loop (<= 3 attempts),
S = single shot (1 attempt). The **only** difference between arms is the attempt budget.

### Arm R — closed-loop recovery

| trial | attempts | displacement | signed | cos | max lift | terminal | passed | evidence_status | failure class |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R/t1 | 1 | 149.07 mm | 152.45 mm | +0.99999 | 1.82 mm | **true** | false | COMPLETE_EVIDENCE_CONTRADICTS_PUSH | FAIL_OVERSHOOT |
| R/t2 | 2 | 65.16 mm | 5.58 mm | **-0.99269** | 2.08 mm | false | false | INCOMPLETE_OR_INVALID_EVIDENCE | FAIL_DIRECTION |
| R/t3 | 2 | 141.05 mm | 133.45 mm | +0.99981 | **7.20 mm** | false | false | INCOMPLETE_OR_INVALID_EVIDENCE | FAIL_LIFT |
| R/t4 | 3 | 95.59 mm | 77.37 mm | **-0.99897** | 2.64 mm | false | false | **INVALID_INFRA (Tooling)** | FAIL_DIRECTION |
| R/t5 | 2 | 116.00 mm | 22.06 mm | **-0.99673** | 0.15 mm | false | false | INCOMPLETE_OR_INVALID_EVIDENCE | FAIL_DIRECTION |

`R/t1` needs three separate statements, because three different things happened at once: the
**terminal clause passed** (149.07 mm, 0.93 mm under the frozen 150 mm ceiling); the
**independent evidence layer rejected it** on the `gripper` gate (finger aperture travelled
3.057 mrad against the 2 mrad bound); and the **skill's own result** reported
`ERR_DISPLACEMENT_OVERSHOOT (error_code 36)` having delivered 152.4 mm against a 90 mm request —
its detail string says *"this is a shove, not a bounded push"*. So the skill itself knew it had
overshot; the end-state geometry happened to land inside the band anyway.

`R/t3` is the first measured **lift** violation in the recovery arm: geometry was fine
(141.05 mm, cos 0.99981, 41.11 mm from the zone centre of a 60 mm radius) but the object rose
7.20 mm against the frozen 5 mm bound.

### Arm S — single-shot control

| trial | attempts | displacement | signed | cos | max lift | terminal | passed | evidence_status | failure class |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S/t1 | 1 | 176.28 mm | 86.24 mm | +0.99940 | 0.84 mm | false | false | INCOMPLETE_OR_INVALID_EVIDENCE | FAIL_ZONE + above_max |
| S/t2 | 1 | 73.93 mm | 0.92 mm | **-0.99976** | **6.67 mm** | false | false | INCOMPLETE_OR_INVALID_EVIDENCE | FAIL_DIRECTION |
| S/t3 | 1 | 117.32 mm | 115.07 mm | +0.99833 | 0.10 mm | **true** | **TRUE** | **COMPLETE** | **PASS** |
| S/t4 | 1 | 124.98 mm | 91.67 mm | +0.99831 | 0.20 mm | **true** | false | COMPLETE_EVIDENCE_CONTRADICTS_PUSH | GATE_GRIPPER |
| S/t5 | 1 | 38.65 mm | 18.89 mm | **-0.99653** | 0.14 mm | false | false | INCOMPLETE_OR_INVALID_EVIDENCE | FAIL_DIRECTION |

`S/t1` is worth care: the trial-time classifier reports one class (`FAIL_ZONE`) while the clause
evidence shows the displacement was **also** 176.28 mm, past the 150 mm ceiling
(`bounds_violated` in `results.tsv` lists both). The single-class label is a limitation of
one-label classification on already-measured trials; it was **not** re-run through the frozen
classifier (`8).

### Arm summary (valid dev trials only)

| arm | n | terminal_passed | passed | evidence COMPLETE | displacement min / median / max / spread |
| --- | --- | --- | --- | --- | --- |
| R (closed loop) | 4 valid (t4 excluded) | 1 / 4 | **0 / 4** | 0 | 65.16 / 141.05 / 149.07 / **83.91 mm** |
| S (single shot) | 5 | 2 / 5 | **1 / 5** | 1 | 38.65 / 117.32 / 176.28 / **137.63 mm** |

**n = 5 per arm cannot order these arms.** With 1 pass in 10 valid dev trials the Fisher exact
comparison is not informative, and the previous round's "4/5 recovery vs 2/5 baseline" headline
is **not reproduced** here (this batch: recovery 0/4, single-shot 1/5). What the data supports
is the *distribution*, not the ranking. Note also that the recovery arm's floor is **lower** than
the single-shot floor in this batch (65.16 mm vs 38.65 mm min) — the opposite of the previous
round's "recovery fixes the near-zero tail" claim. Also a distributional statement on n=5, not
a verdict.

---

## 5. `S/t3` is a genuine pass — from the CONTROL arm

Independently re-derived from the raw bundle (`evidence/S/t3/`, bundle sha256
`021b15a7af105ab6...`, recomputed from the file):

* `task.rest_height_m` = 0.0175 **==** `spec.objects[target].initial_pose[2]` (the rest-height vuln
  the auditor found is not in play; the recorder was given the spec value, and the value handed
  over is recorded separately in `results.tsv`)
* displacement 117.32 mm inside [30, 150]; cos 0.99833; zone centre 18.41 mm of 60 mm
* `max_z` recomputed from the raw physics log = 0.017601685 -> lift **0.1017 mm** (bound 5 mm)
* gripper travel **0.0133 mm**; attachment events 0; max single-step jump 1.63 mm (threshold 30 mm)
* contact intervals 7, `component_present` true, 964 of 1183 motion windows overlap pusher contact
* schema problems: **NONE**; 6620 samples embedded; 0 dropped
* all nine gates true; `terminal_passed` and `passed` both true; `false_success` false

**It must not be cited as evidence that recovery works.** It is the 1-attempt control, and the
closed-loop arm scored 0/4 valid. What it *does* establish is that a decidable `passed=true` is
reachable at all under v0.5.0's nine gates — i.e. the gate stack is not unsatisfiable — which
was the open question this batch existed to answer.

### The gripper gate is discriminating on real data

| trial | aperture travel | gate |
| --- | --- | --- |
| `S/t3` (passed) | **0.000013 rad** | pass |
| `S/t4` (terminal pass, rejected) | **0.004824 rad** | fail |
| `R/t1` (terminal pass, rejected) | **0.003057 rad** | fail |

The passing trial sits **235–371x** below the two rejected ones — a separation of 2.4–2.6 orders
of magnitude, from real runs rather than a calibration fixture. That is evidence *for* the gate's
discriminative power and partially answers the open gripper adjudication: the bound is not
arbitrary, it separates a clean closed-finger push from contact that moves the fingers.

---

## 6. The unseen arm — six trials, all INVALID_INFRA (Environment)

Ordered exactly as the protocol required (R -> S -> U -> U_shot), with the policy frozen before
U. `U` = closed loop <= 3 attempts; `U_shot` = single shot, added at the Lead's request because
the only dev pass came from the single-shot arm.

| trial | attempts | terminal | passed | evaluator read | **actual world-basis** | evidence_status | defect |
| --- | --- | --- | --- | --- | --- | --- | --- |
| U/seed3000 | 1 | false | false | 147.45 mm | **155.32 mm** | INVALID_INFRA | + 3 zero-span contact intervals |
| U/seed3001 | 2 | false | false | 166.21 mm | 158.63 mm | INVALID_INFRA | + 1 zero-span contact interval |
| U/seed3002 | 1 | false | false | 118.05 mm | 145.19 mm | INVALID_INFRA | clean bundle |
| U_shot/seed3000 | 1 | false | false | 45.79 mm | **29.50 mm** | INVALID_INFRA | — |
| U_shot/seed3001 | 1 | false | false | 76.41 mm | 33.14 mm | INVALID_INFRA | — |
| U_shot/seed3002 | 1 | false | false | 54.82 mm | **19.85 mm** | INVALID_INFRA | — |

**0 / 6 passed.** Reported, but **not decidable as a generalisation result**, because the world
that ran was the dev geometry (`0). No trial was rerun: an unwelcome result is not a rerun
reason, and an invalid trial is reported as invalid rather than retried until it looks better.
No parameter was tuned on U.

---

## 7. The recorder defect — found by this lane, and it recurred on unseen data

`benchmark/evidence/recorder.py::contact_intervals()` opens an interval with
`end_sim_ns = start_sim_ns` at the first touching step. A contact observed for exactly **one**
5 ms physics step is therefore emitted as a **zero-length interval**, which `schema.py` rejects as
*"empty or inverted interval"*. One such interval invalidates the **whole** bundle, so all nine
gates become *"not evaluable"*.

Census across the batch (`zero_span_contact_intervals` in `results.tsv`):

| trial | zero-span intervals | schema problems | bundle verdict |
| --- | --- | --- | --- |
| R/t4 | [6] | 1 | invalid |
| U/seed3000 | [9, 10, 12] | 3 | invalid |
| U/seed3001 | [5] | 1 | invalid |
| all other 13 trials | — | 0 | valid |

**Two of the three recovery unseen trials had invalid bundles** — the defect struck the
first-ever unseen measurement, exactly as predicted when it was written up.

### The three-way distinction that keeps the U result honest

It would be easy to write "the unseen arm was unmeasurable". That would be wrong. Three
different situations occurred, and they are not the same:

1. **U/seed3000, U/seed3001 — terminal failure AND invalid evidence (both true).** The terminal
   clause failed on `unmoved:target_box_b`, which is computed from ground-truth poses and does
   **not** depend on the bundle. So *something* was measured independently of the evidence layer.
   (What it measured is a spawn offset, not robot motion — see `0 — which is why these trials are
   INVALID_INFRA for a different reason.)
2. **U/seed3002 — terminal failure AND valid evidence.** Clean bundle, zero schema problems,
   fully measured. Its failure is a real graded result of the dev-geometry world.
3. **The six are not "unmeasurable" as a group.** 5 of 6 had schema-valid bundles; the thing that
   voids them is the *world*, not the *evidence pipeline*.

What is **not** claimed: that any of these six is a pass, a failure, or a generalisation
measurement. They are none of the three.

### Why the corrupt bundles were not hand-patched

I found this defect in my own pipeline. The corrupt bundles (`R/t4`, `U/seed3000`, `U/seed3001`)
are stored **verbatim**, exactly as the recorder produced them, and the trials are labelled
INVALID_INFRA with the reason — not a robot failure and not a pass. Editing the JSON would have
removed the zero-length interval and let the gates run; every downstream number would then have
been computed from a file that no longer matched what the simulator produced, and the "invalid"
case would have silently become a pass-or-fail. The whole point of the four-state discipline is
that *"we could not measure this"* must remain visible. It is the difference between this batch
and one that reports a clean number nobody can check.

---

## 8. Freeze discipline (U was measured against a frozen policy)

`scripts/freeze_policy.py` wrote `evidence/policy_freeze.json` **before** arm U, covering **16 files**:
the policy, the frozen push contract, the push server, `evaluate.py`, `recorder.py`, `verify.py`,
`schema.py`, `sim_profile.py`, this directory's four trial-pipeline scripts, and the three unseen task
specs. `scripts/verify_freeze.py` re-checks them afterwards:

```
$ python3 scripts/verify_freeze.py evidence/policy_freeze.json
FREEZE_OK -- all 16 covered files match the pre-U fingerprint
```

Two documented nuances, neither of which weakens the freeze:

* **The driver's sha256 differs between R/S and U.** Before U I appended a 723-byte *documentation
  paragraph* to `run_evidence_push.py` recording the ceiling guard's known first-attempt limitation.
  Proof that nothing executable changed: removing exactly those 723 bytes reproduces sha256
  `25871671...` — the hash the arm-S manifest recorded — byte-for-byte.
* **The freeze check initially FAILED, and that is reported rather than hidden.** I edited
  `aggregate_results.py` after U (nested-arm support, `invalid_reason`). `verify_freeze.py` caught it.
  Rather than redefine the freeze to accommodate the edit, the edit was **reverted** (the frozen
  file is byte-identical again) and the enhancement moved to a separate post-freeze reporting
  script, `aggregate_results_v2.py`, which only reads trial records that already exist and cannot
  change a measurement. A freeze you relax when it trips is not a freeze.
* **git HEAD moved after the freeze** (`a6fe30af` -> `66eccbc9`) because the Lead committed docs and
  acceptance dirs. `git diff a6fe30af..HEAD` over every covered source path is **empty**, so no file
  that can influence a T08 verdict changed.

---

## 9. What every trial recorded

Per trial (`evidence/<arm>/<trial>/`):

```
evidence_bundle.json         full telemetry incl. every sample (0.6-2.6 MB)
verdict.json                 frozen evaluate.py v0.5.0 output, all 9 gates
trial_record.json            the row that appears in results.tsv
evaluator_input.json         exactly what the evaluator was handed
gt_before.json gt_after.json ground truth from the live world (gz pose stream)
recovery.json                policy verdict + per-attempt decisions + guard
push_XX.json                 every PushObject result, verbatim
logs/physics_steps.jsonl.gz  per-physics-step pose log    (gzip; sha256 in raw_log_manifest.json)
logs/contact_steps.jsonl.gz  per-physics-step contact log (gzip; sha256 recorded)
logs/joint_states.jsonl.gz   /joint_states over the window (gzip; sha256 recorded)
logs/stack.log driver.log    launch + driver output
*_steps_sample.jsonl         first 200 rows, human-readable preview
sim/world.sdf                the exact world this trial ran (ContactTrace injected)
```

Two files are deliberately **not** committed (see §.gitignore§): §evaluator_input.json§
(derived — it is exactly §{objects: gt_after, evidence: bundle}§ and both inputs are committed,
so it is regenerable; 28 MB across 16 trials) and the uncompressed §logs/*.jsonl§ (only the §.gz§
form is kept). Every other artefact above is in git.

The raw per-step logs were gzip-compressed after the batch to keep the worktree committable
(326 MB -> 36 MB). This is reversible and auditable: `evidence/raw_log_manifest.json` records the
sha256 and row count of every log **before** compression, and a pre-archive census verified that
every sample embedded in every `evidence_bundle.json` came from those rows (all 16 trials
consistent, 139,036 log rows total). The bundles — the artefact the verifier actually reads — are
untouched.

### How `results.tsv` was produced, and the two scripts

* `scripts/aggregate_results.py` — **frozen** before U; original table generator.
* `scripts/aggregate_results_v2.py` — post-freeze reporting pass. Adds nested-arm support,
  `invalid_reason`, `counts_toward_denominator`, `bounds_violated` (every bound the frozen clause
  evidence shows as violated, not just the classifier's single label), `spec_vs_world_offset_m` and
  `failure_class_rechecked`. It re-reads frozen `verdict.json` files; it never re-grades.

`results.tsv` lives in **two** places, identical content: the deliverable root
(`evobot_t08_evidence_loop_20261112/results.tsv`, **16 data rows**) and
`evobot_t08_evidence_loop_20261112/evidence/results.tsv`. Columns include everything the Lead
requested: `trial, task_id, arm, seed, attempts, recovery_outcome, displacement_mm, displacement_signed_mm, direction_cos, dist_to_zone_mm, max_lift_m, max_z_from_physics_log, max_z_passed_to_evaluator, terminal_passed, passed, evidence_status, physical_outcome, failed_gates, failed_clauses, failure_class, failure_category, guard_bound, false_success, bundle_sha256, run_id, task_sha256, rest_height_from_spec, rest_height_declared_to_recorder, contact_height_m, contact_rows, physics_rows, joint_rows, zero_span_contact_intervals, wall_s, loadavg_before, loadavg_after, git_head, gz_version, ros_distro, ros_domain_id, invalid_reason, bundle_problems, counts_toward_denominator, failure_class_rechecked, bounds_violated, spec_vs_world_offset_m`.

---

## 10. Failure-class counts (valid dev trials only, n = 9)

| class | count | category | what it means |
| --- | --- | --- | --- |
| `FAIL_DIRECTION` | **4** | Control | cosine ~ -1: the block was driven **backwards** |
| `FAIL_LIFT` | 1 | Control | rose 7.20 mm against the 5 mm bound (R/t3) |
| `FAIL_OVERSHOOT` | 1 | Control | skill delivered 152.4 mm against a 90 mm request (R/t1) |
| `FAIL_ZONE` | 1 | Control | 176.28 mm past the ceiling and outside the zone (S/t1) |
| `GATE_GRIPPER` | 1 | Grasp | aperture moved 4.82 mrad against the 2 mrad bound (S/t4) |
| `PASS` | **1** | — | `S/t3` |
| `INVALID_INFRA` | 1 | Tooling | `R/t4`: zero-span contact interval invalidated the bundle |

**FAIL_DIRECTION is 4 of 9 valid dev trials (44%)**, and the sign census is 4 negative / 5
positive cosine. Combined with the earlier single-shot rounds (3/5 backwards), the **backwards
flick is the most reproducible phenomenon in this task**, across two independent arms. The
mechanism is **UNKNOWN** — the measured shape is "the end effector does not maintain a stable
contact face, so whether the block goes forward or is flicked backwards depends on the contact
instant". An iterative retry policy cannot repair contact geometry, which is consistent with
recovery scoring 0/4 valid.

---

## 11. CONFIRMED vs NOT_RUN

**CONFIRMED (measured this batch, reproducible from the files here)**

| claim | evidence |
| --- | --- |
| A complete 9-gate evidence bundle can be captured in the **same run** as the push | 16/16 trials: physics 2560–5430 rows, contact 2600–5432 rows, joint 1181–2642 rows, `ContactTrace` present in every `sim/world.sdf`, `component_present` true, 0 dropped samples in every valid bundle |
| `passed=true` is reachable under v0.5.0 | `S/t3`, 9/9 gates, rest height bound to spec, bundle sha256 recomputed from disk |
| The rest-height vuln is closed in this batch | `rest_height_from_spec == rest_height_declared_to_recorder` in all 16; independent `max_z` recomputed from the raw physics log equals the value handed to the evaluator in all 16 |
| A `PushObject` can overshoot its request by 69% | `R/t1`: 152.4 mm delivered for a 90 mm request, `error_code=36` |
| A lift violation occurs in the recovery arm | `R/t3`: 7.20 mm against 5 mm |
| The recorder zero-span defect is real and recurs | 3 trials, including 2 of 3 recovery unseen trials |
| The benchmark cannot instantiate a task's declared initial poses | `0, `scripts/audit_geometry.py` |
| Gazebo hygiene | 16 runs, `flock /tmp/evobot_sim.lock` held for each batch, `pgrep '[g]z sim'` empty before every trial, **0 orphans** (gz sim / parameter_bridge / robot_state_publisher / composite_server / push_server) after every trial |

**NOT_RUN / NOT CLAIMED**

* **No generalisation measurement exists.** All six unseen trials are INVALID_INFRA (`0, `6).
* **No comparison of recovery vs single-shot.** 0/4 vs 1/5 on dev; n is far too small to order them.
* **No statement that recovery fixes the near-zero tail.** This batch's floors are 65.16 mm (R) and 38.65 mm (S) — the opposite direction from last round, on n=5.
* **Root cause of the backwards flick is UNKNOWN.** The shape is measured; the mechanism is not.
* **`evobot_heldout_n6_20261111/` is not re-verified** against the `0 spawn defect. Status UNKNOWN.
* **`z_tracker.log` was not produced.** The per-trial `max_z` comes from the Gazebo **physics-step log**
  (every step, 5 ms) rather than the 20 Hz ROS pose sampler `evobot_z_tracker.py`. The step log is
  strictly stronger evidence — it cannot miss a lift inside a sampling gap, which is the failure
  mode `z_tracker.py`'s own docstring warns about — so `z_tracker.log` is recorded here as
  **NOT_RUN (superseded by a denser channel)**, not as captured.
* **No `set_pose` workaround was attempted** for `0. Deliberately.
* **No held-out isolation test** was re-run this batch.
* **`evaluate.py`, `verify.py`, `schema.py`, `recorder.py`, `push.py`, `push_server.py`, `sim_profile.py`,
  `benchmark/tasks/**` and every numeric threshold: unchanged.** Zero edits.

---

## 12. Reproduce

```bash
cd /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp/setup/acceptance/evobot_t08_evidence_loop_20261112

# 1. Re-derive the geometry verdict this batch's honesty rests on (no Gazebo)
python3 scripts/audit_geometry.py

# 2. Re-derive every row of results.tsv from the archived trial records (no Gazebo)
python3 scripts/aggregate_results_v2.py evidence evidence/results.tsv R S U U_shot

# 3. Confirm nothing that can influence a T08 verdict changed after the freeze
python3 scripts/verify_freeze.py evidence/policy_freeze.json

# 4. Inspect any single trial
python3 -c "import json;print(json.dumps(json.load(open('evidence/S/t3/verdict.json')),indent=2))"
```

Full re-run of the batch (needs the Gazebo lane; **one** simulator at a time):

```bash
bash scripts/run_batch.sh <outdir> R ../../benchmark/tasks/t08_dev/T08-push-seed2000.json 5 3 0.0200 0.140
bash scripts/run_batch.sh <outdir> S ../../benchmark/tasks/t08_dev/T08-push-seed2000.json 5 1 0.0200 0.140
```

The world is generated by the **untouched** `sim_profile.py` and the `ContactTrace` plugin is injected
into the **copy** (`scripts/inject_contact_evidence.py`), because `sim_profile.py` refuses `contact_trace`
outside the 2 ms detachable-joint profile and its output is hashed into frozen declarations.

---

## 13. Cost

| item | value |
| --- | --- |
| LLM / paid API calls | **0** |
| Gazebo runs | **16** (5 R + 5 S + 3 U + 3 U_shot) |
| Simulator wall time inside trials | 494 s (8.2 min); whole batch well under an hour |
| Orphans left behind | **0** after every trial, and 0 at batch end |
| Files changed outside this directory | **0** |
| Frozen files edited | **0** |
