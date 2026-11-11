# Adjudication: is R/t1's gripper-gate rejection a true or a false rejection?

**Date** 2026-11-12 · **Decided by** Team Lead · **Status: NOT RESOLVED — deliberately.**
**Inputs:** independent validation lane's re-grade; Lead re-derivation from URDF + raw bundles.

---

## 1. Why this needed an adjudication at all

`R/t1` is the only T08 trial this round with `terminal_passed=true`: displacement 149.07 mm (gate
30–150 mm), direction cosine 0.99999, inside the zone at 49.07 mm of a 60 mm radius, max lift 1.82 mm
against 5 mm. **All nine gates were evaluated. Exactly one failed: `gripper`**, on
`aperture_travel_rad = 0.003057` against `limit_rad = 0.002`.

The validation lane reported this as a probable **false failure** and proposed that the limit is a
**units error** (0.002 "rad" should be 0.040 rad). That would turn R/t1 into the round's first
`passed=true`. **A change that converts a FAIL into the round's headline SUCCESS must be examined
far harder than a change that does the reverse**, so I re-derived it from the robot model rather
than accepting either the lane's reading or the producer's.

## 2. The units claim is WRONG — verified against the robot model

```
/home/ros/agentic_workcell_ws/install/share/open_manipulator_description/urdf/
    open_manipulator_x/open_manipulator_x.urdf

<joint name="gripper_left_joint"  type="prismatic">   <axis xyz="0 1 0"/>
    <limit effort="1000" lower="-0.011" upper="0.02" velocity="4.8"/>
<joint name="gripper_right_joint" type="prismatic">   <axis xyz="0 -1 0"/>
    <limit effort="1000" lower="-0.011" upper="0.02" velocity="4.8"/>
```

The joints are **prismatic**, not revolute. Their position is a **linear displacement in metres**, so
`0.002` is **2 mm of finger travel** — which is exactly what the comment at `fixtures.py:190-192`
says it is ("2 mm separates the two cleanly"). There is no mm-to-rad conversion error. The lane's
arithmetic ("2 mm of finger travel = 0.040 rad for a 50 mm link") assumes a revolute joint that this
robot does not have.

**However, the lane's instinct that something is wrong is correct, and its investigation found the
right trial.** Two real defects sit underneath, and neither is the one it named.

## 3. Defect A (real, low severity): the field name lies about its unit

`max_aperture_change_rad` — the suffix says radians, the value is metres, and it is compared against a
prismatic joint's position. This is not cosmetic: it is precisely what caused a careful independent
auditor to conclude there was a 20× units error, and it would cause the next reader to do the same.
`verify.py:339` even reports the number back as `limit_rad`. **A field whose name asserts a unit it
does not have is the same class of defect as the mislabelled A′ column** — a label nothing verifies.

## 4. Defect B — **WITHDRAWN.** My argument was wrong; the independent lane refuted it

I claimed the gate cannot distinguish a grasp from contact, on the grounds that R/t1's aperture
(`[-0.002960, +0.000096]`) sits in the same *absolute* region as this project's archived
`GRASPED_AT_GOAL` records (`position ≈ −0.00107`).

**That compares the wrong quantity.** The gate bounds **travel**, `max(span) − min(span)`
(`verify.py:329`), not absolute position. Recomputing with travel, from the actual artifacts:

| Case | Travel | vs 2 mm limit | Gate outcome |
| --- | --- | --- | --- |
| Nominal grasp (open `+0.020` → closed ≈ `−0.0013`, n=15 archived picks) | **21.05 mm** | **10.5×** | rejects — **correct** |
| **R/t1 push** (n=1666) | **3.06 mm** | **1.5×** | rejects |
| Known non-grasp push (937-sample calibration run) | **0.00099 mm** | **0.0005×** | passes — correct |

A real grasp is **10.5×** the limit; a known push is **0.0005×**. **The 2 mm bound does separate the
two measured classes.** My "same region" observation was about absolute positions, which the gate
never looks at. The lane also correctly refused to quote an absolute finger gap, because the finger
links are collision **meshes** with no `<box size>` in the URDF — so the inner-face offset is not a
measured quantity. I had reasoned from a number the robot model does not contain.

### 4.1 What survives, and it is a different hole

The gate measures **motion**, never **enclosure**. Fingers already closed *around* an object and then
dragged would show travel ≈ 0 and **pass**. That is a real hole, it is not R/t1's case, and **no change
of the number can fix it** — it needs a different observable (e.g. object velocity correlated with
finger motion, or the carry layer's own attach state). Recorded as the standing defect.

### 4.2 R/t1 is therefore **UNRESOLVED**, not a false rejection

The only non-grasp push ever measured has travel `0.00099 mm`; a nominal grasp is `21.05 mm`.
**R/t1's 3.06 mm lies inside an interval containing no non-grasp measurement.** A threshold set inside
an unmeasured interval cannot be judged right or wrong from existing data:

- calling R/t1 a **false** rejection asserts a calibration nobody performed;
- calling it a **true** rejection asserts 2 mm is justified when it was a round number ~2000× above a
  single observation.

**So I withdraw "probable false failure" — my own earlier framing — and the lane withdraws it too.**
The honest state is UNRESOLVED, and it is the *same* conclusion my §5 already forced: the limit needs
calibration before it can be used to decide anything.

## 5. What I will NOT do

I will **not** raise the limit, rename the field, or re-grade R/t1 as a pass this round.

The reason is not caution for its own sake. Converting R/t1 to `passed=true` would:
- change what "success" means for the round's headline result,
- do so on the strength of an argument I constructed *after* seeing that the trial failed,
- and hand the round a "first genuine T08 pass" whose only supporting change is a threshold I
  loosened myself.

That is the exact failure mode the mission forbids ("修改冻结验收规则制造成功"), and it does not stop
being forbidden because the argument happens to be a good one. **The correct order is: calibrate the
gate against measurement first, then re-grade — not re-grade, then justify.**

## 6. What would actually settle it (the experiment, fully specified)

The question "what does a genuine grasp look like on this robot" is **measurable** and has never been
measured. One controlled run answers it:

| Arm | Action | Expected aperture signature |
| --- | --- | --- |
| G1 | Command a genuine grasp of the 35 mm block (close until `stalled` or `reached_goal`), record `gripper_left_joint` span | excursion on the order of the finger travel needed to reach the block; object visibly held |
| G2 | The T08 push (already have: R/t1) | 3.06 mm excursion, fingers near closed, object never held |
| G3 | Closed-finger sweep with no object present | baseline servo/contact noise floor |

If G1's excursion is **well separated** from G2's, a threshold exists and can be justified by data —
whatever number it lands on. If G1 and G2 **overlap**, then aperture travel alone cannot distinguish
grasp from contact on this robot, and the gate needs a different observable entirely (e.g. object
velocity correlated with finger motion, or the carry layer's own attach state), not a different number.

Cost: 2 Gazebo runs, no model calls. **This is the highest-value 2-run experiment available**, because
it decides whether the round's best T08 trial was wrongly rejected and simultaneously produces the
calibration the gate has always lacked.

## 7. Consequence for the round's claims (unchanged)

| Claim | Status |
| --- | --- |
| R/t1 terminal clause passed | **CONFIRMED** — displacement, direction, zone, lift all inside the frozen bounds |
| R/t1 `passed` | **false**, and it stays false this round |
| R/t1 is a false failure | **WITHDRAWN — UNRESOLVED.** The units argument is refuted (§2) and my own "same aperture region" argument is refuted (§4). 3.06 mm lies in an unmeasured interval between a known push (0.001 mm) and a nominal grasp (21.05 mm) |
| The gripper gate's 2 mm bound is calibrated | **NO — untraceable to any measurement.** `evaluate.py:328` calls it "calibrated" with no citation. It does, however, separate the two *measured* classes (10.5× vs 0.0005×), so it is not obviously wrong — it is unvalidated |
| The gate can distinguish grasp from contact | **PARTLY** — it separates the measured classes by travel, but it measures **motion, never enclosure**, so a pre-closed drag passes (§4.1) |
| T08 acquired | **NO** — unchanged |

## 8. Reproduce

```bash
python3 setup/acceptance/evobot_lead_gripper_gate_adjudication_20261112/aperture_analysis.py
```

Reads the URDF from the installed workspace and `R/t1/evidence_bundle.json`. No simulator, no model calls.

---

## 9. Revision log (kept because this document is itself a judgement, and judgements get reviewed)

| Revision | What changed | Why |
| --- | --- | --- |
| v1 | Reported R/t1 as a probable **false failure** caused by a **units error** (0.002 rad → 0.040 rad) | the independent lane's initial reading |
| v2 | **Units claim REFUTED** (§2) — the joints are prismatic, so 0.002 already means 2 mm. Two real defects substituted: the field-name/unit mismatch, and a claimed discrimination failure | Lead re-derivation from the URDF |
| **v3 (this)** | **My own discrimination argument (§4) WITHDRAWN.** It compared absolute aperture positions; the gate bounds travel. Recomputed: nominal grasp 21.05 mm (10.5×), known push 0.00099 mm (0.0005×), R/t1 3.06 mm (1.5×). The bound **does** separate the measured classes. R/t1 is **UNRESOLVED**, not a false rejection | the independent lane refuted it; the Lead reproduced the refutation |

**What survived all three revisions:** the units *naming* defect, the fact that the 2 mm bound is
**untraceable to any measurement**, the "motion-not-enclosure" hole, and the **decision not to touch
the threshold this round**. The direction of the round's conclusion never depended on the part that
was wrong — which is the only reason it is safe to keep the conclusion.

---

## 10. Second correction (after the full 10-trial batch): the distribution now exists, and it shows false rejections

The §4.2 "UNRESOLVED" verdict rested on the fact that only **one** non-grasp push had ever been
measured. That is no longer true. Ten trials now exist, and nine have gripper telemetry:

| Trial | Aperture travel | Gate | terminal_passed | passed |
| --- | --- | --- | --- | --- |
| **S/t3** | **0.0130 mm** | ✅ | true | **true** |
| S/t5 | 0.0270 mm | ✅ | false | false |
| R/t2 | 0.1320 mm | ✅ | false | false |
| S/t2 | 0.2340 mm | ✅ | false | false |
| S/t1 | 0.9700 mm | ✅ | false | false |
| R/t5 | 1.0370 mm | ✅ | false | false |
| R/t3 | 1.2870 mm | ✅ | false | false |
| **R/t1** | **3.0570 mm** | ❌ | **true** | false |
| **S/t4** | **4.8240 mm** | ❌ | **true** | false |

*(R/t4's bundle is invalid for the recorder defect, so it has no gripper evidence and is excluded.)*

### What this establishes

**The 2 mm bound rejects 2 of 9 ordinary non-grasp pushes (22 %), and both rejections are trials whose
terminal clause PASSED.** R/t1 and S/t4 are the only two trials this round that satisfied the frozen
terminal geometry and were then stopped by the gripper gate alone.

So the earlier "unresolved" framing was too kind to the gate. With n=9 the gate has a measurable
**false-rejection rate of 22 %** among pushes, and it is the sole blocker on two otherwise-passing runs.
Meanwhile the one clean pass sits **154× below the limit** (2.0 mm / 0.013 mm) and **235× below the
smallest trial that exceeded it** (3.057 mm).

### What this still does NOT establish

- It does **not** show the limit should be raised to a specific number. The distribution is **bimodal with
  a gap**: 7 trials at 0.013–1.29 mm, then 3.06 and 4.82 mm. **No trial falls between 1.29 mm and 3.06 mm.**
  A threshold anywhere in that gap would separate these nine samples — but with no measurements inside it,
  any cut point is a post-hoc choice, which is exactly what §5 forbids.
- It does **not** re-grade R/t1 or S/t4. They stay `passed=false`.

### The honest statement

**The 2 mm bound is demonstrably too tight in practice (22 % false rejection), and the data does not
contain the information needed to pick a correct value.** That is an argument for the G1/G2/G3
calibration experiment in §6, not for a new number. The correct fix may well not be a number at all —
see the "motion-not-enclosure" hole in §4.1.

**One thing this does add to §4:** the passing trial's travel is three orders of magnitude below the
rejected ones, so the gate *is* measuring something real. It is not noise, and it is not vacuous in the
way the n=1 sample suggested. It is mis-calibrated, not meaningless.
