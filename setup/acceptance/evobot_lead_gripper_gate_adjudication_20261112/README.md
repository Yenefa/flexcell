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

## 4. Defect B (real, and it is the one that matters): the gate cannot distinguish contact from grasp

The gate bounds **total aperture travel** and calls any excursion beyond the bound "fingers closing on
an object". It never checks whether the aperture could **physically enclose the object**, which is the
only thing that makes a grasp a grasp.

Measured, from `R/t1/evidence_bundle.json`, 1666 samples of `gripper_left_joint`:

```
min = -0.002960 m   max = +0.000096 m   travel = 0.003057 m
```

The commanded open position for this stack is `gripper_open_position: 0.02` (`params.yaml:40`) and the
closed stop is `-0.011` (`:41`). The fingers sat within **3.1 mm of the closed end** for the entire
window, i.e. essentially shut, and the 3.06 mm excursion is that closed-finger pose flexing under
contact.

For comparison, the project's own archived pick sequences record
`gripper_close.position ≈ -0.00107` at `classification: GRASPED_AT_GOAL` — **the same region of
travel** as this "grasp". So the gate's 2 mm bound is narrower than the aperture variation this
project's own nominal grasps exhibit. A gate that would flag the nominal behaviour is not measuring
what it claims.

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
| R/t1 is a false failure | **PROBABLE BUT NOT ESTABLISHED** — the units argument is refuted; the "gate cannot distinguish contact from grasp" argument is strong but needs G1/G2 |
| The gripper gate's 2 mm bound is calibrated | **NO — untraceable to any measurement.** `evaluate.py:328` calls it "calibrated" with no citation |
| T08 acquired | **NO** — unchanged |

## 8. Reproduce

```bash
python3 setup/acceptance/evobot_lead_gripper_gate_adjudication_20261112/aperture_analysis.py
```

Reads the URDF from the installed workspace and `R/t1/evidence_bundle.json`. No simulator, no model calls.
