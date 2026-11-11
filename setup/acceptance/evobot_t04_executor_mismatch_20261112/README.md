# T04-train-seed1000: executor says FAILED, independent verifier says PASS

**Date** 2026-11-12 · **Lane** exec-mystery · **Task** shared task-4
**Repo** `project-033-flexcell/wt-comp`, branch `autonomous/flexcell-remediation`
**Subject instance** `T04-train-seed1000`, archived run `composite-9a4946e2f13e4f2b`
**Evidence root (read-only)** `ci-public-window/evidence/b_realexec_diff5_20261112/T04-train-seed1000/`

---

## 0. Verdict

**H1 is confirmed. H2 is killed by an exact-zero measurement.**

But H1 here is **not** the already-approved P1 signature, and it is **not a second bug**.
It is the *same* defect class seen from a different side: **the place skill's success
predicate tests a mechanism that is not the one performing the release.** The jaws never held
the box (`attach_gap_m = 0.1646 m`), so the aperture test is not *wrong about the jaws* — it
is **irrelevant to the release**, and the skill treats it as decisive.

This distinction is not cosmetic: it decides **where the fix belongs** (§4b). Conclusion:
**the predicate error is in `place_server.py`; the contract layer is behaving correctly and
must not be changed to compensate.**

**The known P1 defect's scope must widen** — in *description* (mechanism, not field
signature) and in *blast radius* (it also destroys measurement provenance), not in location.

Additionally, an independent defect was found in the benchmark spec itself (§5), and one
widely-quoted metric (`verdict.false_failure`) is shown to carry **zero information** (§6).

---

## 1. The two competing hypotheses

| | Claim |
| --- | --- |
| **H1** | The skill layer mis-reported a real release as a failure (known P1 family); the object was genuinely placed. |
| **H2** | The executor genuinely failed mid-episode and the object reached the goal **incidentally** (inertia, or being shoved), so the PASS is luck. |

These imply different things about which numbers may be quoted, so the difference had to be
measured, not argued.

---

## 2. The discriminating observation

**The object did not move laterally after the failure was declared. Not "barely" — exactly zero.**

```
place.jsonl  place.object_before_release  = [0.12515345487641943, -0.14727041380856554, 0.025066787390113778, 0,0,0,1]
gt_after.json target_box_b              = [0.12515345487641943, -0.14727041380856554, 0.01749490653803553, 0]
```

```
object_before_release[0] === gt_after.target_box_b[0]   ->  true   (bit-for-bit)
object_before_release[1] === gt_after.target_box_b[1]   ->  true   (bit-for-bit)
lateral displacement release -> final                   ->  0.000e+0 m   (exact zero)
vertical displacement release -> final                  ->  -7.572 mm    (pure gravity settle)
```

**Why this kills H2.** H2 requires the object to *arrive* at the goal after the failure —
by inertia, sliding, or being shoved. Any such arrival is lateral motion. The measured
lateral motion is **exactly 0.0 m**: the two X/Y values are not merely close, they are the
same floating-point numbers. The only thing that changed between the release and the final
ground-truth snapshot is **Z**, by 7.57 mm, which is the box settling under gravity onto the
table (rest height 0.0175). A box cannot slide into a bin by zero metres.

**And the goal predicate was already satisfied before the failure was written:**

| quantity at `object_before_release` (t = release) | value | threshold | satisfied? |
| --- | --- | --- | --- |
| distance to `zone_1` centre `[0.12, -0.15]` | **0.005832 m** | radius 0.06 | **yes**, 10.3x inside |
| height error vs rest `0.0175` | **0.007567 m** | REST_HEIGHT_TOLERANCE_M 0.02 | **yes** |
| `inside_zone` / `resting` | true / true | — | **yes** |

So the placement clause `placement:target_box_b` was **already true at the moment of
release**, 1.10 s before the executor wrote its failure. Nothing "reached the goal
incidentally" afterwards; the goal was reached **before** the failure existed.

---

## 3. Timeline (wall_unix_seconds, base 1794419712.2810662)

All timestamps from `sim/skills/move_to_pose.jsonl` (`execution_start`/`execution_end`),
`sim/skills/carry.jsonl` (`wall_ts`), `sim/skills/place.jsonl` (`wall_ts`).

```
  rel(s)   wall_unix        event
  ------   -------------    --------------------------------------------------------------
  -2.316   1794419709.966   move target_box_b-hover    START
  -0.001   1794419712.280   move target_box_b-hover    END  outcome=SUCCEEDED
   0.063   1794419712.344   move target_box_b-grasp    START
   1.070   1794419713.351   move target_box_b-grasp    END  outcome=SUCCEEDED
   2.541   1794419714.822   move target_box_b-lift     START
   4.011   1794419716.292   move target_box_b-lift     END  outcome=SUCCEEDED   box_rise 0.098 m
   6.021   1794419718.302   PICK record written        outcome=0
   6.224   1794419718.505   move target_box_b-hover    START (carry leg)
   7.731   1794419720.012   move target_box_b-hover    END  outcome=SUCCEEDED
   7.798   1794419720.079   move target_box_b-descend  START
   9.266   1794419721.547   move target_box_b-descend  END  outcome=SUCCEEDED   EE z=0.19177
   9.602   1794419721.883   carry RELEASED             carry.jsonl: event=stop cause=release engaged=true
   ---      ---             <-- GOAL ALREADY SATISFIED HERE (0.005832 m inside zone_1) -->
  10.704   1794419722.985   PLACE record written       outcome=1 error_code=25 released=false
```

**Every motion succeeded.** Hover, grasp, lift, carry-hover, descend: 5/5
`outcome=SUCCEEDED`, `position_error_m` max 0.00447 m. The failure is **not** a motion
failure; it is raised 1.44 s after the last successful motion, by the release predicate.

---

## 4. Why this is NOT the approved P1 signature (the critical distinction)

The approved P1 record (`setup/acceptance/evobot_release_mechanism_20261111/`) states the
mechanism as: *the carry layer detached the object (release happened) while the jaw did not
reach the commanded aperture (a real stall); the skill fails on the aperture test alone.*

That reading assumes **the jaws were holding the object**. Here they were not.

```
pick.jsonl  pick.attach_gap_m   = 0.1646372671311612      (EE-to-box distance at "attach")
pick.jsonl  pick.carry_offset   = [0.0016295636367400501, 0.0015105521615796647, -0.16462227213514669]
```

The box centre is **0.1646 m below the end-effector link**. The two jaws cannot span that
gap — the object is nowhere near the fingers. The "grasp" is a
`velocity_servo` **pin** (`carry_backend: velocity_servo`, params.yaml:64), which
constrains the box pose to follow the EE at that frozen offset. It is not a friction grasp.

Consequences, stated exactly:

1. `gripper did not open (position=-0.011 requested=0.02 stalled=True)` is a **true
   statement about the jaws** and an **irrelevant statement about the release**. The jaws
   were never closed on the box, so their aperture cannot release it.
2. The **actual release is `carry_release_confirmed=true`** — the carry pin was removed at
   1794419721.883, and the box then fell 7.57 mm onto the table.
3. `place.released = false` is **not** an independent observation. It is simply the
   never-executed default: `place_server.py:426-434` returns on the aperture test
   **before** `res.released = True` at line 435. The field is false because the function
   returned early, not because a release was measured and found wanting.
4. `-0.011` is the **closed** position (`gripper_close_position: -0.011`, params.yaml:41).
   The jaws sat at the closed stop and never moved. So the aperture test is comparing the
   *closed* pose to the *open* command — guaranteed to fail, independent of the box.

**Therefore:** the approved P1 fix ("treat `carry_release_confirmed` as the release
signal; demote the aperture stall to a degraded attribute") would *also* have corrected this
run. But the P1 **description** is incomplete: it says the skill mis-grades a *real grasp
release*, whereas here there was never a grasp to release. Anyone re-validating the P1 fix by
looking for a "stalled jaw that failed to let go of the object it was holding" will not find
that pattern in this instance, and may wrongly conclude the fix does not cover it.

---

## 4b. Where the fix belongs: `place_server.py`, NOT the contract

> **Status of this section: a LOCATION conclusion, not an authorisation.**
> It answers *where* a P1 fix would belong. It does **not** approve, schedule, or license any
> edit to `place_server.py`. That file is a runtime safety contract; changing it remains
> `requires_human_approval: true, approved: false` (goal §13). Anyone who cites this section to
> justify editing the skill layer is misusing it — cite it only to say *where* the fix belongs.

This was checked against the contract layer rather than inferred. **Conclusion: the predicate
error is local to `place_server.py`; the contract layer is correct and must not be widened to
compensate.** Four independent lines of evidence:

**(1) The contract already carries the right signal, and the skill discards it.**
`PlaceObject.action` exposes both `bool released` and `string detail`, and the skill writes
`carry_release_confirmed=true` into its own record in the *same* `finish()` call
(`place_server.py:411` then `:430`). Nothing in the interface prevents reporting the carry
confirmation as the release. The information is present and the skill chooses the other field.
A contract change would therefore be redundant — the interface is not what lost the signal.

**(2) The contract's downstream gates are deliberately built to be unfoolable, and they work.**
`native_success()` (`contracts/composite.py:210-226`) does **not** trust the skill's verdict:
it re-checks `terminal_status`, `outcome`, `error_code`, `run_id`, `episode_path`,
`goal_uuid` identity, and requires `object_at_place is True` plus a finite
`final_position_error_m <= tolerance`. `push_native_success()` goes further and re-derives
success from *measured displacement and direction cosine* — quantities "the skill cannot fake".
This is exactly the right posture, and it is why the executor produced a *typed, traceable*
`error_code=62` rather than a silent wrong answer. Weakening it so that a place failure could
be reinterpreted upstream would remove the project's best defence against false success.

**(3) Recovery eligibility is deliberately frozen to *never* retry a PLACE.**
`contracts/recovery.py:16-17`: *"PLACE / OBSERVE: never recoverable (failures abort; a
carried box is not retried)"*, and `recovery_eligible()` returns `False` for anything that is
not PICK/VERIFY. This is the **correct** safety rule: you must not re-command a place whose
outcome is uncertain. It is also why a mis-reported place failure is **terminal** — the run
cannot self-heal, so the cost of the predicate bug is a whole lost task, not a retry. That
raises the *priority* of fixing the predicate; it does not move the fix into the contract.
Changing `recovery.py` to retry PLACE would be strictly more dangerous.

**(4) The contract layer's own error taxonomy already names this correctly.**
`ERR_PLACE_FAILED = 25` is a *skill-specific failure*; the task-level `TASK_ERR_SKILL_FAILED =
50` is produced by the executor. The chain 25 → 50 → 62 is a faithful, correctly-typed
propagation of *what the skill claimed*. Every layer above the skill did its job. Only the
bottom layer's claim was wrong. A fix anywhere above the skill would be compensating for a
lie rather than removing it.

**So:** the defect is a **scope error in one predicate** — "jaw aperture" is the wrong
mechanism to interrogate for "was the object released" — and it lives entirely inside
`place_server.py`. Per the Lead's instruction and goal §13 this remains the **P1 item gated on
human approval**; **no edit to `place_server.py`, `PlaceObject.action`, `recovery.py`, or
`composite.py` is proposed or made here.** This section states a *location conclusion*, not a
patch.

---

## 5. A separate defect in a *different layer*: the T04 goal is partly vacuous

> **Layer note, to avoid conflation:** this is **not** a second bug in `place_server.py`.
> §4/§4b concern the *runtime* success predicate (one defect, one location). This section
> concerns the *benchmark spec / measurement instrument* — a wholly independent layer that
> would be wrong even if the release predicate were perfect. The two findings share no code
> path and must be fixed and approved separately.

`placement:target_box_a` required **no work at all**.

```
T04 spec: target_box_a initial_pose = [0.22, 0.0, 0.0175]
          zone_2 pose              = [0.25, 0.05, 0.0175], radius 0.06
          distance at t=0          = 0.058310 m  ->  INSIDE (margin 0.001690 m)
```

`verdict.json` clause 1 confirms it: `distance_m = 0.05831`, `radius_m = 0.06`,
`inside_zone = true`, and `gt_after.json` shows `target_box_a = [0.22, 2.523e-20, 0.017499...]`
— byte-identical to its initial pose. **The box was never touched, and the clause was free.**

### Say it plainly

**"T04-train-seed1000 PASS" is real, but one of its two clauses was free.**

**It is NOT a false pass.** Be precise about why, because the two statements get conflated:

| clause | earned? | evidence |
| --- | --- | --- |
| `placement:target_box_b` | **earned** | box moved from `[0.2, -0.18]` to `[0.125153, -0.147270]` — a genuine 0.0854 m transport, measured by ground truth, ending 0.005832 m from the zone centre (radius 0.06). The robot really picked it up, carried it, and released it there. |
| `placement:target_box_a` | **free** | already 0.05831 m from `zone_2` at t=0 (radius 0.06); `gt_after` shows it byte-identical to its initial pose — never touched. |

So the run genuinely demonstrated a pick-carry-place of **one** object into **one** bin. The
verdict is correct on the world it measured; what is overstated is the **task's** implied
demand. `T04_duplicates` asks for a *duplicate-ordering* capability — two objects routed by a
distance-based rule — and this instance could only ever test **one** of the two routings,
because the other was pre-satisfied by the world generator.

**Precision matters for the rest of the round's claims:**

- It is **wrong** to say "T04-train-seed1000 failed but was graded pass" — the place genuinely
  succeeded physically and was mis-reported; §2–§4 establish that.
- It is **also wrong** to say "B solved T04-train-seed1000, a two-object duplicate-ordering
  task" — only one object was ever routed.
- The **safe** claim is: *B executed one genuine pick-carry-place into the correct bin, and the
  executor mis-reported it as a failure. The instance does not test duplicate ordering,
  because its second clause was satisfied before the episode began.*

Neither the PASS nor the false negative is invalidated by the vacuity finding. They are two
independent facts about the same run, and both must be stated for the round's numbers to be
honest.

### Scope of the vacuous-clause problem (full scan, not sampled)

All 72 `benchmark/tasks/train/*.json` were re-derived with the evaluator's own
`_dist2d(initial_pose, zone.pose) <= zone.radius` rule:

| class | instances | meaning |
| --- | --- | --- |
| **ALL** placement clauses satisfied at t0 | **4** | goal is **fully vacuous** — passes with zero motion |
| SOME (>=1 but not all) satisfied at t0 | **12** | one free clause each |
| none satisfied at t0 | 56 | clean |

- The 12 "some" cases are **every T04 instance** (`T04-train-seed1000` … `1011`):
  `target_box_a -> zone_2` is free in all twelve.
- The 4 "all" cases are `T05-train-seed1001`, `1007`, `1009`, `1010`
  (`T05_relay`): `expected_goal.placement = {target_box_a: zone_2}` with
  `target_box_a` already 0.05831 m from `zone_2`. Those four specs are satisfied **before
  the robot moves**; they can only distinguish behaviour through the `visit` clause.

This is a **spec/evaluator** finding, not a runtime finding. It is reported, not fixed —
`benchmark/tasks/**` and the evaluator's numeric clauses are frozen and would need human
approval.

---

## 6. `verdict.false_failure` carries zero information in these runs

`evaluate.py:254` reads `claimed = bool(final_state.get("agent_claimed_success"))` and
`:344` sets `false_failure = bool(passed and not claimed)`. In the archived B runs there is
**no `observation.json`** (confirmed absent for this instance), so `claimed` is `None` →
`False`, and `false_failure` is `True` **whenever `passed` is true, for any reason**.

Measured across all 9 B executions: `passed=true`, `agent_claimed_success=false`,
`false_failure=true`, `false_success=false` — **identically for all 9**, including the 8
that succeeded normally with no defect at all.

**So `false_failure=true` on T04 is not evidence of anything.** Quoting it as
confirmation of the executor/verifier mismatch would be a measurement error. The mismatch is
established instead by `composite.json` `outcome=1` vs `verdict.json` `passed=true`,
which is a genuine disagreement between two independent judgements.

### The general rule (do not quote `false_failure` outside this condition)

> **`false_failure` is only defined for runs where an agent actually made a claim.**
> It is computed as `passed and not agent_claimed_success` (`evaluate.py:254, :344`), and
> `agent_claimed_success` defaults to `None`/`False` when the field is absent from the
> final state. In a run with **no claim**, `false_failure` degenerates to `== passed` and
> therefore reports `true` for every passing run **regardless of whether any executor defect
> occurred**. It measures *claim calibration*, not executor correctness.
>
> Corollary: `false_failure` and `false_success` are **only meaningful as a pair**, on runs
> where a claim exists. Quoting `false_failure=true` from a claim-less run as evidence of a
> harness defect is a category error — it will be `true` on perfectly healthy runs.

This is not hypothetical: **all 9** archived B executions have
`agent_claimed_success=false` (no `observation.json` exists in those directories), so all 9
report `false_failure=true` — including the 8 with no defect whatsoever. Any future claim of
the form "false-failure rate = N" computed over such runs is measuring `passed`, nothing more.

---

## 7. Four separate states (no inflation)

| state | value | evidence |
| --- | --- | --- |
| **planning_correct** | **yes** | `composite.json` `goal.stages = ["target_box_b-0","target_box_a-1"]`; destinations `[0.12,-0.15]` and `[0.25,0.05]` match `expected_goal.placement`. Order differs from A′ but the mapping is identical and the spec constrains no order (`constraints.order = []`). |
| **execution_succeeded** | **NO** (executor) / **YES** (physical subtask) | `composite.json:15` `outcome=1`, `:16` `error_code=62`, `:18` `completed_stage_ids=[]`. But the physical move b→zone_1 did succeed: box moved 0.0854 m into the zone and settled at 0.005832 m error. |
| **independent_evaluation_passed** | **yes** | `verdict.json:5` `passed=true`, `:6` `terminal_passed=true`, `:45` `failed_clauses=[]` (evaluator v0.5.0). |
| **agent_claimed_success** | **no** | `verdict.json:46` `agent_claimed_success=false`; `observation.json` absent, so nothing was claimed at all. |

The executor's own failure text is accurate about its own bookkeeping —
`detail = "native terminal/verification unconfirmed for target_box_b-0"` — it is the
*place skill's* verdict it propagated, not a failure of the motion chain.

---

## 8. 10-category attribution

**Primary: State Management.**

The place skill's own success predicate conflates two different questions — *"did the jaws
reach the commanded aperture?"* and *"was the object released?"* — and treats the first as
the second (`place_server.py:426-434`). Worse, it returns on that test **before** recording
any physical outcome, so the failure path has no `box_after` and no `place_error_m`
(confirmed: neither key exists in `place.jsonl`; the early return at 426-434 precedes the
settle at 439 and the retreat at 461). A layer that fails before measuring cannot
distinguish "failed" from "succeeded but I stopped looking" — which is exactly what happened.

**Secondary: Tooling / Environment** (benchmark spec, §5): 16 of 72 train instances contain a
placement clause already satisfied at t0, and 4 are fully vacuous. This is not a runtime bug;
it is a measurement-instrument defect that inflates apparent capability.

**Explicitly NOT the cause:**
- *Kinematics* — all 5 motions SUCCEEDED, max position error 0.00447 m.
- *Control* — descend reached EE z=0.19177 vs target 0.1895 (0.00447 m error), well inside tolerance.
- *Grasp* — the "grasp" is a velocity_servo pin by design (`carry_backend: velocity_servo`);
  the 0.1646 m EE-to-box offset is the **declared** carry geometry, not a grasp failure.
- *Planning* — plan matches the spec's placement mapping.
- *Perception* — the ground-truth sampling is correct and consistent (`gt_after` equals the
  live pose at release to the bit).
- *Model Reasoning* — no model call in this path; the policy is `fsm` 1.0.
- *Runtime* — no crash, no timeout; `error_code=50` is a clean policy ABORT.

---

## 9. Which numbers may be quoted

| claim | status |
| --- | --- |
| "T04-train-seed1000 executor outcome=1 / error_code=62" | **quotable** — `composite.json:15-16` |
| "T04-train-seed1000 independently graded PASS by evaluate.py v0.5.0" | **quotable** — `verdict.json:5` |
| "This is a false negative: the object was genuinely placed" | **quotable, now proven** — lateral displacement after release = 0.000e+0 m; goal satisfied 1.10 s before the failure |
| "H2 (incidental arrival by inertia/shove)" | **refuted** — requires lateral motion; measured lateral motion is exactly zero |
| "B's T04 pass demonstrates a two-clause duplicate-ordering capability" | **NOT quotable** — one of the two clauses (`target_box_a`) was free at t=0 (§5) |
| "`false_failure=true` proves the mismatch" | **NOT quotable** — true for all 9/9 runs including 8 clean ones (§6) |
| "B execution success rate is 8/9" (by `composite_outcome`) | **NOT quotable as capability** — the 1 "failure" is a proven false negative, so the executor-outcome metric understates; but the *task* metric is also inflated by vacuous clauses. Neither number is clean. |
| "T04-train-seed1000 was a genuine mid-episode failure" | **NOT quotable** — refuted |
| "The known P1 defect fully explains this run" | **NOT quotable as stated** — the field signature matches but the mechanism differs (§4); the *predicate* is the same defect, the *story* is not |
| "This is a second, separate bug" | **NOT quotable** — it is one predicate error, same location (§4b) |
| "The fix belongs in the contract layer / `PlaceObject.action`" | **NOT quotable** — contract already carries the signal and its gates are correct (§4b) |

---

## 10. Does the known P1 defect's scope have to widen?

**Yes — in two directions.**

1. **Mechanism, not just signature.** The approved P1 record is keyed on a *field pattern*
   (`released=False`, `carry_release_confirmed=True`, `reached_goal=False`,
   `GRASP_STALLED`). This instance reproduces that pattern **exactly** while the physical
   story is different: there was no grasp to release, the object hung 0.1646 m below the EE
   on a velocity_servo pin, and the jaws sat at their closed stop the whole time. The P1
   family must be defined as *"the skill derives release-success from jaw aperture instead of
   from the carry layer"*, not as *"a real grasp release mis-graded by a jaw stall"*.
   Otherwise a reviewer checking only the grasp-release story will judge the fix incomplete
   for this case, or will add a grasp-specific special case that misses it.

2. **Blast radius beyond release.** The same early-return defect also destroys measurement
   provenance on **every** aperture-failure path: because the skill returns at line 430, it
   never reaches `rec['box_after']` (line 448) or `rec['place_error_m']` (line 450). So on
   any such run the project loses the primary physical measurement and must fall back to
   `verify.jsonl` — which is precisely the degradation the P1 proposal already predicted
   (`place_box_after_will_be_recorded: true`). This instance confirms that prediction
   empirically: `box_after` and `place_error_m` are **absent** from `place.jsonl`.

**Both widenings are of *description* and *blast radius*, not of *location*.** The predicate
error stays in `place_server.py` (§4b); the contract layer must not be widened to absorb it.
Neither widening requires changing a threshold, the evaluator, `push.py`, `recovery.py`, or
`PlaceObject.action`. Both are descriptions of the existing defect.

**Scope of this document: evidence chain + scope conclusion only.** Per goal §13, the P1 item
is explicitly gated on human approval. **No edit to `place_server.py`, the release contract, or
any contract module is proposed or made here** — the fix remains a separate, approved
decision. The P1 proposal stands at `requires_human_approval: true, approved: false`.

---

## 11. What is still UNKNOWN, and the one run that would settle it

**UNKNOWN: the rate.** This is **n=1**. Everything above is a single archived run read in
full. Nothing here measures how often the aperture-failure path fires, and the P1 record's
own "9 cases" come from *other* batches whose `attach_gap_m` was never recorded, so it is
**not known whether those 9 also had the 0.1646 m pin geometry or were genuine grasp
releases.** That is the one open question that changes the fix's shape.

**Exact missing artifact:** `pick.attach_gap_m` and `pick.carry_offset` for the 9 runs
listed in `setup/acceptance/evobot_release_mechanism_20261111/mechanism.txt`
(`evobot-batch2` / `evobot-batch3`, run ids `HO-*`). Those runs' `pick.jsonl` were not
archived into this worktree; only their `place` rows were extracted into `mechanism.txt`.

**One extra run that would settle it:** re-execute any **one** of those 9 `HO-*` instances
with the current tree and the same params, and read `pick.jsonl` →
`attach_gap_m` / `carry_offset[2]`. If it is ≈0.16 m the pin geometry is universal and the
P1 fix must be stated as "release = carry-layer confirmation, jaws are irrelevant". If it is
≈0.0 m those 9 were genuine grasp releases and the two mechanisms coexist, requiring the
wording to cover both. **I did not run this** — the sim lane owns the Gazebo lock, and this
lane was scoped to read-only diagnosis.

### Handed forward (open item, not solved here)

This UNKNOWN is **handed to the next round** as a named experiment; it is not a gap in this
document, it is the one question this document deliberately leaves open.

| field | value |
| --- | --- |
| **question** | Is the 0.1646 m pin geometry universal across the P1 family, or do genuine-grasp releases coexist with it? |
| **why it matters** | Decides the *wording* of the P1 fix: "jaws are irrelevant" vs "cover both mechanisms". Does **not** change the fix location (§4b). |
| **blocking artifact** | `pick.jsonl` (`attach_gap_m`, `carry_offset`) for the 9 `HO-*` runs in `evobot_release_mechanism_20261111/mechanism.txt` — not archived in this worktree |
| **one experiment** | Re-execute any **one** `HO-*` instance, same params, read `pick.attach_gap_m` |
| **decision rule** | ≈0.16 m → pin geometry universal · ≈0.0 m → both mechanisms coexist |
| **blocker on running it** | Gazebo lock owned by the sim lane; this lane is read-only diagnosis |
| **status** | **OPEN — handed forward, credited to this lane** |

---

## 12. Reproduction (read-only, no Gazebo)

```bash
# the discriminating measurement
python3 - <<'PY'
import json
R='ci-public-window/evidence/b_realexec_diff5_20261112/T04-train-seed1000/'
p=json.loads(open(R+'sim/skills/place.jsonl').read().strip())
g=json.load(open(R+'gt_after.json'))['objects']['target_box_b']
obr=p['object_before_release']
print('XY bit-identical :', obr[0]==g[0] and obr[1]==g[1])
print('lateral move (m) :', ((obr[0]-g[0])**2+(obr[1]-g[1])**2)**0.5)
print('vertical  move(m):', g[2]-obr[2])
print('dist to zone_1   :', ((obr[0]-0.12)**2+(obr[1]+0.15)**2)**0.5)
PY
```

Expected: `XY bit-identical : True`, `lateral move (m) : 0.0`,
`vertical move(m): -0.007572`, `dist to zone_1 : 0.005832`.

Vacuous-clause scan: re-derive `_dist2d(o.initial_pose, zone.pose) <= zone.radius` over all
`benchmark/tasks/train/*.json` with `expected_goal.placement`; expect 4 fully-satisfied and
12 partially-satisfied.

---

## 12b. Revision note (v2, after Lead review)

Three corrections were made on the Lead's review, plus one new section:

| change | reason |
| --- | --- |
| §0/§4 wording: "second distinct mechanism" → **"predicate tests a mechanism that is not the one performing the release"** | The physical release *was* the carry pin; the jaw test is **irrelevant, not wrong**. Calling it a second bug would misdirect the fix. |
| **§4b added — fix location** | The Lead asked which layer owns the fix. Checked against the contract modules rather than inferred: **`place_server.py`**, not the contract. |
| §6 **general rule** added for `false_failure` | It is only defined when an agent made a claim; it degenerates to `== passed` otherwise. |
| §5 **"say it plainly"** added | "T04-train-seed1000 PASS is real but one of two clauses was free" — and explicitly **not** a false pass. |

The Lead independently re-derived the vacuity counts with a separate scanner
(72 specs / 4 fully vacuous / 12 partial) and wrote them up separately in
`setup/acceptance/evobot_lead_benchmark_vacuity_20261112/`, so that finding does not depend on
this lane's artifacts.

**No code or contract change is proposed in this document.** The P1 fix remains gated on human
approval.

---

## 13. Files read (all read-only, nothing modified)

```
ci-public-window/evidence/b_realexec_diff5_20261112/T04-train-seed1000/
  composite.json                                  outcome=1, error_code=62
  verdict.json                                    passed=true, false_failure=true
  gt_after.json                                   final ground truth
  stack.log                                       ROS/gz log, carry RELEASED lines
  sim/skills/place.jsonl                          the failure record (1 line)
  sim/skills/pick.jsonl                           attach_gap_m, carry_offset
  sim/skills/move_to_pose.jsonl                   5 motions, all SUCCEEDED
  sim/skills/carry.jsonl                          81 events, release at 1794419721.883
  sim/skills/task_fsm.jsonl                       FSM abort, NON_RECOVERABLE
  sim/skills/decisions.jsonl                      4 decisions
  sim/skills/composites/composite-9a4946e2f13e4f2b.jsonl
  sim/episodes/pick_place_v1_pick_place_v1-3a5018f5.json   4 steps, full world state
  sim/params.yaml, sim/world.sdf
comparison (read-only):
  ci-public-window/evidence/b_realexec_20261112/T0{1,2}-*       4 passing runs
  ci-public-window/evidence/b_realexec_diff5_20261112/T04-*1001,1002, T06-*   4 passing runs
  ci-public-window/evidence/baseline_a_v2_gated_20261111/T04-train-seed1000/
  benchmark/tasks/train/*.json (72)              vacuous-clause scan
  benchmark/evaluators/evaluate.py v0.5.0        clause semantics
  src/flexcell/flexcell_skills/flexcell_skills/place_server.py
  src/flexcell/flexcell_skills/flexcell_skills/pick_server.py
  src/flexcell/flexcell_skills/flexcell_skills/carry_server.py
  src/flexcell/flexcell_skills/flexcell_skills/common.py
  src/flexcell/flexcell_skills/flexcell_skills/contracts/composite.py
  setup/acceptance/evobot_release_mechanism_20261111/   approved P1 record
  setup/acceptance/evobot_gripper_false_negative_measured_20261112/README.md
  setup/acceptance/evobot_p0_paired_20261112/README.md
```

**Modified:** only this directory. No Gazebo launched. No git commit.
