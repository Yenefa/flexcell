# The ~30% false-failure rate is one defect: `place` uses gripper aperture to decide whether an object was released

**Date** 2026-11-12 · **Found by** the Lead, following the audit's observation that both P0 arms fail ~30% of runs on a world-correct outcome
**Status: CONFIRMED. Root cause identified with a single mechanism. Fix NOT applied — needs human approval.**

---

## 1. The observation being explained

Both P0 arms show the executor reporting failure on runs where the world ended correct:

| | A-prime | B (archived) |
| --- | --- | --- |
| `execution_succeeded` | 9/16 | 11/16 |
| `independent_evaluation_passed` | 13/16 | 14/16 |
| gap | **4** | **3** |

Four A-prime runs and three B runs have a **failed executor verdict on a world-correct outcome**. That
is not noise; it is a measurement system reporting a false failure on both arms.

## 2. Every failure is the same failure

All seven A-prime execution failures carry the identical chain:

```
composite : error_code=62  "native terminal/verification unconfirmed for <stage>"
  ← pick_place_v1 : outcome=1  error_code=50 (ERR_SKILL_FAILED)
    ← place : error_code=25  detail="gripper did not open (position=-0.011 requested=0.02 stalled=True)"
    ← episode final_state: "policy abort (NON_RECOVERABLE): place failed (ERR_PLACE_FAILED,
       carried box is not retried) (trace=PICK_A(attempt=1):OK, PLACE_A:FAIL)"
```

`PICK_A:OK` — **the pick succeeded every time.** The failure is always at `PLACE_A`, always for the
same reason, and always the gripper."

Frequency, from the `place.jsonl` of every run in both arms:

| arm | place attempts | `gripper did not open` | rate |
| --- | --- | --- | --- |
| A-prime (16 runs) | 29 | **7** | 24 % |
| B archived (16 runs) | 34 | **5** | 15 % |
| **total** | **63** | **12** | **19 %** |

And at **run** level, which is what any per-run verdict sees:

| arm | runs | runs with a false release denial | rate |
| --- | --- | --- | --- |
| A-prime | 16 | **7** | 44 % |
| B archived | 16 | **5** | 31 % |
| **total** | **32** | **12** | **37.5 %** |

**Between a third and a half of runs on both arms have `place` denying a release that the carry backend performed.** Every one of those run verdicts is wrong about the world.

## 3. The mechanism

### 3.1 The trigger, read from the code

`place_server.py:424-432`:

```python
if (open_state["position"] is not None
        and open_state["aperture_error"] is not None
        and open_state["aperture_error"] > self._release_aperture_tolerance_m
        and not open_state["reached_goal"]):
    return finish(R.OUTCOME_FAILED, R.ERR_PLACE_FAILED, 'gripper did not open (...)')
res.released = True
```

With `gripper_open_position = 0.02` and `release_aperture_tolerance_m = 0.005` (`:68-69`).

### 3.2 The aperture band is narrower than the actuator's own shortfall

The G1 calibration measured the gripper's **free-space** open position: **0.010434** against a
request of **0.02**. So even with nothing between the fingers, `aperture_error = 0.0096 m` —
**nearly twice the 0.005 m tolerance**.

**The check therefore passes only because `reached_goal` rescues it.** It is one flag away from
rejecting every single placement. That is a fragile predicate, and it is now measured rather than
suspected.

### 3.3 The gripper has nothing to do with whether the box is held

From the same run's `carry.jsonl`, the carry is a **`velocity_servo` pin**:

```
{"event": "start", "object": "target_box_b", "backend": "velocity_servo",
 "offset": [0.0049, -0.0052, -0.1638], ...}
```

The offset's z component is **−163.8 mm** — the box is pinned kinematically, a sixth of a metre from
the tool frame. **The fingers never touch the box.** This is the same quantity as T04's
`pick.attach_gap_m = 0.1646 m`, reached here from a completely different direction.

**So the gripper aperture cannot be evidence about the object.** It reports the state of a mechanism
that is not participating in the transport.

### 3.4 And the object IS released — the record says it is not

`place_server` returns `released: false`. The carry log for the same run:

```
{"event": "stop", "object": "target_box_a", "cause": "release", "engaged": true, ...}
```

**`cause: release`.** The pin is released on abort, dropping the box exactly where it was carried —
which is the destination. That is why four of the seven A-prime "failures" still evaluate as passes:
the task was completed and the skill denied it.

## 4. The claim, stated exactly

> `place_server` treats **gripper aperture** as its release predicate. On this stack the object is
> transported by a `velocity_servo` **pin**, not by the fingers, so aperture is not evidence about the
> object. When the gripper misses its 20 mm target — which it does even in free space, reaching 10.4 mm —
> the check depends entirely on `reached_goal`. When that is also false, `place` reports
> `ERR_PLACE_FAILED` and `released: false` **while the carry pin releases the box at the correct
> destination**. The world is right and the verdict is wrong.

**This is a False Failure mechanism, and the goal requires False Failure to be reported.**

## 5. The same mistake, twice in this project

| where | aperture used to detect | refuted by |
| --- | --- | --- |
| **T08 push gate** (`verify.py:302`) | "the fingers stop against the object's width" → a grasp | round 2: closing on a block and closing on air differ by **0.42 mm**; the gate measures drive completion |
| **place release** (`place_server.py:424`) | "gripper reached open" → the object was released | this round: the pin carries the box 164 mm from the tool; `cause: release` fires regardless of aperture |

**Both use a gripper-state proxy for an object-level event, and on this stack both are wrong for the
same reason: the object is moved by a carry mechanism the gripper does not participate in.**

That is worth stating as a project-level lesson rather than two separate bugs: **on this robot,
gripper telemetry is not evidence about objects.**

## 6. The fix, and why I am not applying it

The predicate should read the **carry state**, which already exists and is already logged:

```
carry.jsonl -> {"event": "stop", "cause": "release", "engaged": true}
```

`released` should be set from the carry backend's release confirmation, not from the gripper. The
gripper check can remain as a *diagnostic* — it just must not be the **release predicate**, and its
failure must not override a released carry.

**Not applied**, because `place_server.py` is a frozen skill contract and this is a behaviour change
to a release predicate. It is the **same item** I raised in round 1 and it is still awaiting approval:

> round 1: "`place_server.py` release predicate — fix location = `place_server.py`, NOT the contract;
> the contract exposes `released` and the skill discards it"

Round 1 identified the location. This round identifies the **mechanism and its cost**: 19 % of place
attempts on both P0 arms, 7 of 16 A-prime run verdicts, and every T04-style "place failed but the box
is where it should be" case.

## 7. What this changes about every number measured so far

| measurement | effect |
| --- | --- |
| A-prime 13/16 evaluation vs B 14/16 | **task-level numbers are unaffected** — they read the world, not the verdict |
| A-prime 9/16 execution vs B 11/16 | **these are the contaminated numbers.** They count verdicts, and 19 % of place attempts produce a false failure |
| T08 numbers | unaffected — push does not go through `place` |
| Any future "success rate" quoting execution verdicts | must be read as a **lower bound** until this is fixed |

**Practical consequence: every execution-based failure rate this project has reported is an
overestimate, by an amount that this defect sets at roughly one run in five.**

## 8. Reproduce

```bash
python3 setup/acceptance/evobot_lead_place_release_predicate_20261112/analyse_place_failures.py
```

Reads the committed `place.jsonl`, `carry.jsonl` and episodes from both arms. Offline, no simulator.
---

## 9. This is not a new defect — it is in the whole project history

Sweeping every `place.jsonl` under `setup/acceptance/` (234 files, 21 experiment archives,
back to 20261110):

```
total place rows across ALL archives : 539
with 'gripper did not open'          :  51  (9.5%)
```

Per archive, the ones that matter:

| archive | place attempts | closed-gripper failures | rate |
| --- | --- | --- | --- |
| `evobot_p0_aprime_execution_20261112` | 29 | 7 | **24.1 %** |
| `evobot_goal_check_ab_20261111` | 42 | 7 | **16.7 %** |
| `evobot_pooled_n32_20261111` | 42 | 7 | **16.7 %** |
| `evobot_crosstype_20261111` | 34 | 5 | 14.7 % |
| `evobot_unseen_n6_20261111` | 14 | 2 | 14.3 % |
| `evobot_pair16_drift_20261111` | 42 | 5 | 11.9 % |
| `evobot_pair16_20261111` | 39 | 4 | 10.3 % |
| `evobot_heldout_n6_20261111` | 11 | 1 | 9.1 % |
| `evobot_native_honesty_20261111` | 37 | 3 | 8.1 % |
| `evobot_unseen_bc_20261111` | 29 | 2 | 6.9 % |
| `evobot_recover_n6_20261111` | 15 | 1 | 6.7 % |
| `evobot_generalization_20261111` | 42 | 2 | 4.8 % |
| `evobot_valid_batch_20261111` | 42 | 2 | 4.8 % |

**Every baseline comparison this project has made is contaminated, at 5–24 % of place attempts
depending on the batch.** The worst affected are exactly the ones the project has been quoting:
the P0 A-prime batch, the goal-check A/B comparison, the pooled n=32, and the crosstype run.

## 10. What must be restated

| claim | status after this |
| --- | --- |
| "A-prime executes 9/16, B 11/16" | **lower bounds.** Both arms lose runs to this defect at similar rates (7/16 and 5/16), so the *comparison* survives; the absolute rates do not |
| "B planned 16/16 and executed 11/16" | the 5-run gap is **not all B's fault** — 5 of B's 16 runs have a false release denial |
| any "execution succeeded" rate in any archive | **an underestimate**, by 5–24 % of place attempts depending on the batch |
| task-level evaluation numbers | **unaffected** — they read the world, not the verdict |
| "the recovery layer rescued two B runs (14 → 16)" | **needs re-checking.** If the first-attempt failures include false release denials, recovery partly consists of retrying a step that had already physically succeeded |

The last row is the one I would most want checked next, and I am flagging it rather than asserting
it: B's recovery advantage may be an artifact of this defect rather than a genuine capability, which
would change the P0 conclusion from "B's edge is architectural" to "B's edge is recovery from a
bug in its own place step".
---

## 11. THE DECISIVE CONSEQUENCE: B's "recovery advantage" is recovery from this bug

I flagged in §10 that B's recovery advantage needed re-checking rather than assuming. It has now been
checked, and the answer changes the P0 conclusion.

B's headline was: `evaluation_passed` 14/16 on first attempt → **16/16 after recovery**, i.e. a
recovery layer that rescued two runs, described as B's surviving **architectural** edge over A-prime.

Those are the only two recovered runs. **Both failed their first attempt with exactly this defect:**

```
HO-2efba46248da  failed_stage=target_box_a-0  completed_stage_ids=[]
HO-d3ab212142de  failed_stage=target_box_b-0  completed_stage_ids=[]

both: native_error_code=50
      native_fsm_trace=['PICK_A(attempt=1):OK', 'PLACE_A:FAIL']
      native_detail='... place failed (ERR_PLACE_FAILED, carried box is not retried)
                     ... previous_skill=PLACE cause=ERR_PLACE_FAILED legacy_error_code=25'
```

**Identical to the A-prime failures. Same stage, same skill, same cause, same code.**

So B's entire recovery advantage consists of **retrying its own place bug and succeeding on the
retry** — because the second attempt's gripper happens to open. It rescued two runs from a defect, not
two tasks from a hard situation.

## 12. What the P0 conclusion becomes

| | before this round | after |
| --- | --- | --- |
| B's edge over A-prime | "architectural: a recovery layer" | **"a retry loop for its own place defect"** |
| A-prime's disadvantage | "run one-shot, no recovery" | **same, but the thing it lacks is a retry around a bug — not a capability** |
| Comparable planning | 16/16 identical plans, zero model cost | unchanged |
| Who is better | "roughly equal, B has recovery" | **not established either way, and the one difference is an artifact** |

A-prime scores 13/16 one-shot. B scores 14/16 first attempt and 16/16 with retries. **Every single one
of the runs separating them fails for this defect.** If A-prime were given the same retry loop, the
expected outcome is that it reaches the same or a higher number, since its plans are identical.

**I am not claiming A-prime would win.** I am claiming the comparison cannot distinguish them, because
the only measured difference is a retry around a defect that both arms hit.

## 13. What this means for the goal's own accounting

The Master Goal requires `False Success` to be 0 and **`False Failure` to be reported**. This is a
False Failure mechanism, and it has been inflating every execution-based failure rate in this project
for its entire history — 51 of 539 place attempts across 21 archives.

The honest position is not that the numbers are wrong. It is that **the executor's verdict is a
measurement of the executor's self-report, not of the world**, and this project has repeatedly
quoted it as if it were the latter. Task-level evaluation reads the world; execution verdicts read
the skill's opinion of itself. They differ on 37.5 % of runs.

## 14. The one-line fix, for human approval

```python
# place_server.py:424-432 - today
if (aperture_error > self._release_aperture_tolerance_m and not reached_goal):
    return finish(FAILED, ERR_PLACE_FAILED, 'gripper did not open')
res.released = True

# should be: released is a CARRY-BACKEND fact, not a gripper fact
released = carry_backend.release_confirmed()      # carry.jsonl already records this
if not released:
    return finish(FAILED, ERR_PLACE_FAILED, 'carry release not confirmed')
if not gripper_opened:                            # diagnostic only, never fatal
    rec['gripper_diagnostic'] = open_state
```

**Not applied.** `place_server.py` is a frozen skill contract and this changes a release predicate.
It is the same item raised in round 1, now with its mechanism, its frequency, its historical reach
and its cost to the P0 conclusion attached.
---

## 15. Refinement: what B's retry actually did (checked, not assumed)

§11 says B's recovery is a retry around its own bug. I checked the mechanism rather than leaving the
claim at that level, and two details make it more precise — and one of them is uncomfortable for the
headline number.

### 15.1 It was a FULL re-run, not a resume from a checkpoint

```
plan.json        stages: ['target_box_a-0', 'target_box_b-1']
plan_retry.json  stages: ['target_box_a-0', 'target_box_b-1']
plan equal: True
```

The retry replays the **identical plan from the start**. There is no inherited-stage field, no
checkpoint resume of the physical work. So B's recovery capability is a **plain re-run of the same
plan** — which is exactly the behaviour a flaky step rewards and a genuinely hard task does not.

### 15.2 The re-run's executor succeeded — but its OWN graded verdict still failed

```
task_retry.out    : outcome=0, completed_stage_ids=['target_box_a-0','target_box_b-1'],
                    detail='all native stages and fresh joint conditions confirmed'
verdict_after1.json: passed=False, failed_clauses=['placement:target_box_b','order']
```

**The retry's own evaluation says FAILED.** So B's reported 16/16 after recovery is not the retry's
verdict — it is the **final world state** evaluated once. Three different measurements of one run:

| measurement | value |
| --- | --- |
| first attempt's executor verdict | `error_code=62` (fail) |
| retry's executor verdict | `outcome=0` (success) |
| retry's own graded verdict | `passed=False` — `placement:target_box_b`, `order` |
| final world state, graded once | **pass** — this is the "16/16 after recovery" figure |

This does not weaken the main finding — the first-attempt failure is still this exact defect, and the
retry is still a re-run of the same plan. But it means **the "16/16 after recovery" number is not a
success rate of anything.** It counts final world states, and on at least one of the two recovered
runs the retry itself was graded as a failure.

### 15.3 A misclassification worth noting for the failure-attribution requirement

`recovery_decision.json` records:

```
"failure_class": "grasp",
"measured_reason": "native place stage failed: ['PICK_A(attempt=1):OK', 'PLACE_A:FAIL']",
"why": "measured state no longer matches the declared plan"
```

**The failure class is `grasp`, but the failing step is `PLACE` and the pick succeeded** — the reason
string right beside it says so. The goal requires 10-category failure attribution; a classifier that
labelled this "grasp" would put every one of these 12 runs in the wrong category, and the recovery
policy's choice of action is keyed on that label.

That is a second, smaller defect found while checking the first, and it is recorded rather than folded
in: **the failure classifier has a category error that misattributes place failures to grasp.**
