# Finding F18 — the gripper gate's aperture bound: CORRECTION and adjudication

**Status** my original units claim is **RETRACTED**. The limit is not a units error.
The underlying concern survives in a weaker, correctly-stated form.

---

## 1. What I got wrong (retracted)

I claimed `max_aperture_change_rad = 0.002` was a mm-to-radian confusion, reasoning
that "2 mm of finger travel on a ~50 mm link is 0.040 rad". **That reasoning assumed a
revolute joint.** Verified against the URDF:

```
/home/ros/agentic_workcell_ws/install/share/open_manipulator_description/urdf/
  open_manipulator_x/open_manipulator_x.urdf

<joint name="gripper_left_joint"  type="prismatic"> <axis xyz="0 1 0"/>
  <limit effort="1000" lower="-0.011" upper="0.02" velocity="4.8"/>
<joint name="gripper_right_joint" type="prismatic"> <axis xyz="0 -1 0"/>
  <limit effort="1000" lower="-0.011" upper="0.02" velocity="4.8"/>
```

Both are **prismatic**. A prismatic joint's position is a **linear displacement in
metres**. So `0.002` really is **2 mm**, exactly as `fixtures.py:190-192` says, and
there is **no** mm-to-rad error. My claim is withdrawn.

The Lead was right to refute it, and this is the kind of claim that must not reach a
frozen deliverable uncorrected.

### What *is* wrong: the field name

`max_aperture_change_rad` carries **metres**. `verify.py:339` reports it back as
`limit_rad`, and the gate's reason string says "changed by %.4f **rad**". The name and
the log both assert a unit the quantity does not have. That is what invited my error
and will invite the next reader's — a label asserting something nothing verifies,
the same class as the A-prime mislabel.

**Severity: LOW (naming/documentation).** It cannot admit or reject a run by itself.
Recommended: rename to `max_aperture_change_m` in v1.1.0 and report `limit_m`.

---

## 2. The substantive question: can 2 mm of travel distinguish grasp from contact?

The gate bounds **travel** (`verify.py:329`: `max(span) - min(span)`), not absolute
position. That distinction decides the R/t1 question:

| case | travel | vs 2 mm limit |
| --- | --- | --- |
| nominal grasp (open +0.020 -> closed on object ~-0.0013) | ~21.3 mm | **10.6x over** — correctly rejected |
| R/t1 push | 3.06 mm | 1.53x over — rejected |
| 937-sample calibration push | 0.0000010 m | 0.0005x — accepted |

**A genuine grasp is ~7x further from the limit than R/t1 is.** So the 2 mm bound
does separate a real grasp from R/t1 — which is the opposite of what I said, and also
weaker than the Lead's point B.

### Correction to the Lead's point B

Point B compares **absolute positions**: grasp `gripper_close.position = -0.00107` vs
R/t1 `min = -0.00296`, and concludes the two "are in the same aperture region". That
is true of absolute position but **not** of the quantity the gate measures. Travel is
what is bounded; the absolute position R/t1 sits at says nothing about its travel.
So point B does **not** establish that the gate cannot separate grasp from contact.

I also decline to quote an absolute finger **gap**: the finger links use collision
**meshes** with no `<box size>`, so the inner-face offset is not in the URDF. Any
"gap = 42 mm + 2*pos" figure is an assumption about mesh geometry, and I will not
assert one as measured.

### The real discrimination gap (weaker than claimed, still real)

The gate measures **motion**, never **enclosure**. If the fingers are already closed
around an object and the arm then drags it, travel ≈ 0 and the gate passes. That is a
genuine hole — but it is **not** R/t1's situation, and it is not fixable by changing
the number. It needs a different observable.

---

## 3. Verdict on R/t1: **UNRESOLVED**, not false rejection

I previously reported R/t1 as a probable **false failure** on the strength of the
retracted units argument. Withdrawing that. The honest position:

- Only **one** genuine non-grasping push has ever been measured (the 937-sample run,
  travel 0.0000010 m).
- A nominal grasp travels ~21.3 mm.
- R/t1's 3.06 mm sits **3093x above** the one non-grasp sample and **0.14x** a nominal
  grasp — in an interval with **no measurements at all** on the non-grasp side.

**A limit set inside an unmeasured interval cannot be judged correct or incorrect from
existing data.** Calling R/t1 a false rejection would assert a calibration nobody has
done; calling it a true rejection would assert the 2 mm bound is justified when it was
chosen as a round number ~2000x above a single observation.

**R/t1 keeps `passed=false` under v1.0.0 AND under v1.1.0.** No re-grade on a
threshold change made after seeing it fail.

---

## 4. Required follow-up experiment (specified, NOT run — sim lane owns the lock)

```
G1  genuine grasp of the 35 mm block: close until stalled or reached_goal;
    record the full gripper_left_joint span
G2  T08 push: already have (R/t1, 3.06 mm)
G3  closed-finger sweep with no object: the servo/contact noise floor
```

Decision rule, fixed **before** the runs:

- If `G1_travel` and `G2_travel` are separated by more than the larger of
  `G3_travel` and 3x `G3_travel`, a data-justified threshold exists at their midpoint.
- If they **overlap** within the G3 noise band, aperture travel **cannot** distinguish
  grasp from contact on this robot, and the gate needs a different observable
  (e.g. contact force on the finger links, or object-relative pose) — not a different
  number.

2 runs, no model calls. Until this exists, F18 stays open and R/t1 stays failed.

---

## 5. What this changes in the deliverables

| Item | Change |
| --- | --- |
| `README.md` F18 | retitled; units claim withdrawn; reclassified LOW (naming) + open calibration defect |
| `MIGRATION.md` §4 | rewritten: no threshold change proposed; R/t1 keeps `passed=false` in both versions |
| `reproducers/repro_9gate_audit.py` | F18 asserts the naming mismatch only, not a units error |
| v1.1.0 patches | do **not** touch the aperture limit; may rename the field |
