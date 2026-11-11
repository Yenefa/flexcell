# T08 at the block's centre height: does the push actually work?

**Date** 2026-11-12 · **Task** `T08-push-seed2000` (dev — tuning allowed by the mission) · **n = 1, pre-registered**
**Status: PRE-REGISTERED BEFORE THE RUN. Result recorded below only after it completed.**

---

## 1. What made this worth a run

Rounds 6 and 7 of this session concluded that T08's blocker was **reach** — that the arm physically could not
get its palm below the block's top edge. **That conclusion was wrong, and the repository already contained
the measurement that refutes it.** I had been reasoning from a "first contact at z = 0.0350" figure without
checking it against the contact-height sweep that was already committed.

`setup/acceptance/evobot_t08_saturation_diagnosis_20261112/HEIGHT_SWEEP_RESULT.md` swept the contact height:

| contact_height_m | displacement | contact made |
| --- | --- | --- |
| **0.0175** (block centre) | **151.14 mm** | yes, never lost |
| 0.0200 | 69.92 mm | yes, lost at step 5 |
| 0.0225 | 6.32 mm | yes, lost at step 2 |
| 0.0250 | 3.55 mm | no |
| 0.0300 (old default) | 0.59 mm | no |

**At 0.0175 the same skill pushes the block 151 mm in one continuous contact with direction cosine 0.9994.**
That is not a reach failure — it is a success that overshoots.

And the whole T08 evidence loop ran at **0.0200**: `evobot_t08_evidence_loop_20261112/freeze_policy.py:75`,
`"contact_height_m": 0.0200`, confirmed in that README (§4, *"contact_height_m = 0.0200, n = 5 per arm"*).
**So T08's 0/6 was measured 2.5 mm above the block centre, at a height the sweep shows loses contact.**

The sweep left one question open: it pushed 151 mm because the default overdrive (0.05) adds to the requested
0.09 with nothing to stop it. Nobody has measured the task at the correct height **with the overdrive
controlled**. That is what this run does.

## 2. Pre-registration (written before the run)

**Configuration** — the only two changes from the evidence loop:

```
contact_height_m : 0.0200  ->  0.0175     (block centre)
overdrive_m      : nan (default 0.05) -> 0.005
```

Everything else identical: `T08-push-seed2000`, direction `(-1, 0, 0)`, `distance_m = 0.09`, same world
generation, same runner.

**Reasoning for the prediction.** At 0.0175 the sweep's contact was never lost, so the object should travel
essentially the arm's travel. With `distance_m = 0.09` and `overdrive_m = 0.005`, arm travel ≈ 0.095 m.

**Prediction (falsifiable):**

| quantity | predicted |
| --- | --- |
| displacement | **0.085 – 0.105 m** |
| contact lost | **no** |
| direction cosine | **≥ 0.99** |
| vertical displacement | **≤ 0.020 m** |
| increments executed | 5 (all), none stalled |

**Falsified if** displacement falls outside 0.060–0.140 m, **or** contact is lost, **or** cosine < 0.99,
**or** the object lifts. Any of those and the centre-height hypothesis is wrong too.

**What this run cannot establish.** It is a **dev** instance used for tuning. Even a clean pass would be
**Simulation Tested on one dev instance**, not generalisation — the unseen seeds 3000–3002 were already spent
and are not reusable for a claim after tuning. A genuine generalisation measurement needs fresh instances.

**Harness-failure guard.** If the `push_object` action server does not appear, the run is recorded as
`HARNESS_ERROR` and **not** as a zero-displacement push. Infrastructure failure must not be scored as task
failure.

## 3. Result

One real Gazebo run, `contact_height_m = 0.0175`, `overdrive_m = 0.005`, dev `seed2000`.

```
outcome              : 1        (FAILED)
error_code           : 36       ERR_DISPLACEMENT_OVERSHOOT
displacement_m       : 0.10576
direction_cos        : 0.99914
delta_z_m            : -0.000104
contact_made         : true
contact_lost         : false
increments_executed  : 5        (none stalled)
detail               : object moved 0.1058m, 0.0158m beyond the 0.0900m requested
                       (tolerance 0.0050m); this is a shove, not a bounded push

measured_before      : [0.22000,  0.00000, 0.01750]
measured_after       : [0.11433, -0.00438, 0.01740]
```

### 3.1 My prediction, and how it did

I predicted displacement **0.085 – 0.105 m**. Actual **0.10576 m** — **outside by 0.8 mm**.

**So the numeric prediction is falsified at its own upper bound, and I am not going to call it a confirmation.**
What the run does establish is the *mechanism*: contact was made and **never lost**, the block moved 105.8 mm
along the required direction with cosine 0.9991, and it did not lift (0.1 mm). The arm's travel is about
1.11× the nominal request rather than the 1.00× I assumed when converting overdrive to travel — the block
slides on after the push ends. That arithmetic error is mine, not the skill's.

### 3.2 Graded against the task's own criterion

| sub-clause | requirement | measured | pass |
| --- | --- | --- | --- |
| displacement | 0.030 – 0.150 m | **0.1058** | **yes** |
| vertical | ≤ 0.020 m | **0.0001** | **yes** |
| direction cosine | ≥ 0.90 | **0.9991** | **yes** |
| zone | ≤ 0.060 m from zone centre | **0.0072** | **yes** |

```
ALL FOUR SUB-CLAUSES: True
skill verdict        : outcome=1 ec=36  (overshoot vs the REQUESTED 0.09 m)
```

**The block ended 7.2 mm from the zone centre — comfortably inside a 60 mm radius.** The task was satisfied.
The skill reported failure because the block moved 15.8 mm further than *requested*, against a 5 mm
tolerance.

### 3.3 What this establishes, at what level

| claim | level |
| --- | --- |
| the push skill CAN satisfy the full T08 task clause on this stack | **Simulation Tested, n = 1, dev instance** |
| the blocker was contact height, which is a request field, not the robot | **measured** |
| T08's recorded 0/6 was produced at `contact_height_m = 0.0200`, a height that loses contact | **confirmed from `freeze_policy.py:75` + the height sweep** |
| the skill's verdict rejects a task-satisfying push (5 mm vs the task's 120 mm band) | **measured, 1 case** |

**It does NOT establish generalisation.** It is one dev instance, used for tuning, with n = 1. Unseen seeds
3000–3002 were already spent and are not reusable for a claim after tuning. A generalisation measurement
needs **fresh** instances generated after this configuration was fixed.

### 3.4 What I am NOT claiming

- Not "T08 is solved": one run, one seed, one configuration.
- Not "the skill is broken": it correctly refused a push that went further than asked. Its contract is
  bounded-displacement; the task's contract is a band. They are different and both are honest.
- Not "the 0/6 was false": it was **truly measured**, at a height that was chosen before the sweep existed.
  The useful statement is that **it was measured at the wrong contact height and that height was later shown
  to be the primary factor** — see `evobot_t08_saturation_diagnosis_20261112/`.
