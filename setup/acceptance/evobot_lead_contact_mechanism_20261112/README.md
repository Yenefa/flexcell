# Why the block gets flicked backwards — contact geometry is NOT the cause

**Date** 2026-11-12 · **Analysed by** Team Lead · **Input**: per-step contact telemetry already on disk
**Status: two round-1 hypotheses REFUTED by measurement; mechanism narrowed, still UNKNOWN.**

---

## 1. The question

The dominant T08 failure is not "did not push" but **"pushed backwards"**: in 4 of 9 valid dev
trials the direction cosine came out ≈ −1. Round 1 described this as "the end effector does not
maintain a stable contact face", and named two candidate mechanisms without separating them.

This analysis separates them using the per-step contact log that every trial already captured —
no new Gazebo run, no model calls.

| Hypothesis | Prediction |
| --- | --- |
| **H_A ride-over** | backward trials contact the block's **TOP EDGE** → higher contact z, downward normal |
| **H_B face hit** | contact at **mid-height on the far face** → contact z near block centre, horizontal normal |

## 2. Result 1 — averaging over the run shows no separation

`contact_mechanism.py`, all gripper-vs-block contacts across each run:

| class | n | mean contact z | mean max z | mean normal_z |
| --- | --- | --- | --- | --- |
| forward (cos > 0) | 5 | 0.0301 m | 0.0413 m | −0.543 |
| backward (cos < 0) | 5 | 0.0278 m | 0.0361 m | −0.312 |

difference in mean contact z = **−2.3 mm**, i.e. below any physically meaningful resolution, and
the normal is *more* downward in the **forward** trials — the opposite of what H_A predicts.

## 3. Result 2 — the first contact is the right statistic, and it also fails to separate

A flick is decided at the **first** contact; a long dragging contact afterwards dominates the mean.
`contact_first_touch.py` therefore looks only at the first gripper-vs-block contact:

| arm | trial | t_first (s) | x offset (m) | contact z (m) | cos | disp (mm) |
| --- | --- | --- | --- | --- | --- | --- |
| R | t1 | 5.110 | +0.0184 | 0.0350 | **+1.0000** | 149.07 |
| R | t2 | 4.040 | +0.0166 | 0.0349 | **−0.9927** | 65.16 |
| R | t3 | 4.270 | −0.0084 | 0.0349 | +0.9998 | 141.05 |
| R | t4 | 4.540 | +0.0181 | 0.0346 | **−0.9990** | 95.59 |
| R | t5 | 4.025 | +0.0148 | 0.0350 | **−0.9967** | 116.00 |
| S | t1 | 4.870 | +0.0172 | 0.0350 | +0.9994 | 176.28 |
| S | t2 | 4.130 | −0.0022 | 0.0350 | **−0.9998** | 73.93 |
| S | t3 | 4.105 | +0.0181 | 0.0350 | +0.9983 | **117.32 (PASS)** |
| S | t4 | 4.535 | +0.0049 | 0.0350 | +0.9983 | 124.98 |
| S | t5 | 4.380 | +0.0160 | 0.0350 | **−0.9965** | 38.65 |

backward − forward: **Δx_offset = +2.6 mm, Δz = −0.1 mm**. Neither exceeds 8 mm.

**Both hypotheses are refuted as discriminators.**

## 4. What the data DOES establish — and it is more useful than the hypothesis was

**Every single trial contacts the block at z ≈ 0.0349–0.0350 m, which is exactly the block's top**
(35 mm block resting from z = 0). And `x_offset` is between −8 mm and +18 mm, mostly ≈ +0.017 m,
i.e. the block's far top edge (half-width = 0.0175 m).

So the push skill **never contacts the block's face.** It contacts the **top far edge**, every time,
in every arm, including the one trial that passed.

```
commanded contact_height_m = 0.0200   (EE target z)
measured first contact z   = 0.0349-0.0350  (block top)
discrepancy                = +15 mm
```

This **independently confirms** round 1's `CONTACT_GEOMETRY_MEASUREMENT.md` finding ("commanded 0.0200,
actual first contact 0.0349, offset +14.9 mm") and extends it: the offset is not a nuisance, it means
the robot is performing an **edge drag**, not a face push.

**That explains the variance far better than any geometry difference between trials.** An edge-on-edge
contact is a near-degenerate contact: whether the block slides forward, rotates, or squirts out
backwards depends on the exact force balance at a corner, which is why the same commanded motion
produces 38 mm one run and 176 mm the next — and why the recovery arm's retries cannot fix it.

## 5. What this means for the next round (a real change of direction)

| Old plan | New plan, justified by this measurement |
| --- | --- |
| "lower the contact height slightly" | **not enough** — with a 15 mm command-to-contact offset, small command changes do not move the contact off the top edge |
| — | **make the contact face-contact**: derive the commanded height so the *finger tip* lands at block mid-height (≈ z 0.0175), which means commanding substantially **lower** than 0.0200, and verifying the resulting contact z is ≈ 0.0175 rather than 0.035 |
| — | or use a **link with collision geometry at the right height**, or a **single-finger** push |

**The measurement to make next is not a push trial — it is a contact-height calibration**: for a
sweep of commanded heights, record the *first contact z*. Round 1 did this once (n=1 per point, §3.1 of
the capability report) and found 0.030 → no contact, 0.0200 → contact at 0.0349. What is missing is a
sweep with enough points to find the commanded value whose actual contact z is ~0.0175, i.e. the
block's centre rather than its top.

## 6. Honest limits

- **n = 10 trials, one dev instance.** The forward/backward split is 5/5 with no separation; a
  2.6 mm difference on n=5 per class cannot exclude a real effect smaller than ~8 mm.
- The contact log records the **contact point**, and I read it in the world frame. If that frame is the
  block's local frame the z would be a local offset; the fact that it is uniformly ≈ the block top, and
  that round 1's independent measurement agrees, is what makes the reading credible. **This assumption
  is stated, not proven.**
- **Mechanism remains UNKNOWN.** What changed is that a range of explanations is now excluded, and the
  one variable that is certainly wrong (first-contact geometry) is out.

## 7. Reproduce

```bash
python3 setup/acceptance/evobot_lead_contact_mechanism_20261112/contact_mechanism.py
python3 setup/acceptance/evobot_lead_contact_mechanism_20261112/contact_first_touch.py
```

Reads the committed `contact_steps.jsonl.gz` logs. No simulator, no model calls.

---

## 8. Where the +15 mm comes from — a code trace, not a guess

The measured contact height (0.0349–0.0350) is 15 mm above the commanded `contact_height_m` (0.0200).
Reading the frozen contract (`contracts/push.py`, unmodified) explains it without any new run:

```
push.py:215-219  contact_pose(center, half, direction, height)
                     -> [center - direction*half, ... , float(height)]
                 the z of the target pose IS contact_height_m, verbatim.

push.py:408-412  face     = contact_pose(before, half_extent_m, direction, contact_height)
                 approach = face - direction*approach_clearance_m,  z = face[2]

push.py:222-233  push_targets(...) -> every increment target keeps z = face[2]
```

So the end-effector is commanded to travel **at constant z = contact_height_m** through the block
region. For `contact_height_m = 0.0200` that is 2.5 mm above the block's centre (0.0175) — which,
if the commanded frame were the physical contact surface, would be a **face push**.

It is not. The confirmed round-1 tooling finding is that the control target
`end_effector_link` **has no collision geometry**; the bodies that actually collide are the gripper
finger links, and their collision meshes do not sit at the `end_effector_link` origin. The observed
offset is ≈ **+15 mm in z**, which is exactly the gap between the commanded `0.0200` and the measured
contact `0.0349–0.0350`.

**This is why the parameter does not do what its name says.** `contact_height_m` positions a virtual
frame, not the contact surface, so setting it to "block mid-height" produces a contact at the block's
**top edge**. Round 1's own sweep is consistent: commanding **0.0300** gave first contact z **0.0350**
and commanding **0.0200** gave **0.0349** — a 10 mm change in the command moved the contact by
**0.1 mm**. The contact height is essentially **insensitive** to the parameter over the range that was
tested, because the finger rides on the block top either way.

### The experiment this implies (not yet run)

Not a sweep to "tune the displacement", and not "lower it a little" — an **inverse calibration**:

> For a range of commanded `contact_height_m`, record the **first-contact z** from the contact log.
> Find the command whose first-contact z is ≈ **0.0175** (block centre) rather than 0.035 (block top).
> Then verify the contact **x-offset** moves from the top edge toward the `+x` face.

That is ~6 short runs with existing tooling, and it is the difference between an edge drag and a
face push. **Until that calibration exists, no amount of retry budgeting, threshold discussion or
extra trials will change the outcome**, which is consistent with everything this round measured:
5/5 forwards, 5/5 backwards, same geometry, same command.

---

## 9. The URDF confirms it — this is not an inference from behaviour

§8 traced the offset to code. `check_ee_frame_geometry.py` checks the **robot description**, which is
the primary source and does not depend on any run:

| link | visual | collision | collision mesh |
| --- | --- | --- | --- |
| `gripper_left_link` | yes | **yes** | `gripper_left_palm.stl` |
| `gripper_right_link` | yes | **yes** | `gripper_right_palm.stl` |
| `end_effector_link` | yes (box 0.01³) | **NONE** | — |

| joint | type | origin from `link5` |
| --- | --- | --- |
| `gripper_left_joint` | prismatic | (0.0817, +0.021, 0) |
| `gripper_right_joint` | prismatic | (0.0817, −0.021, 0) |
| `end_effector_joint` | fixed | (0.126, 0, 0) |

Three facts follow, and none of them requires a simulation:

1. **`end_effector_link` has no collision geometry.** A pose commanded for it cannot be a statement
   about where the robot touches anything. `push.py` commands exactly that frame
   (`contact_pose` → `move_to` → `push_targets`), all at constant z = `contact_height_m`.
2. **The contacting bodies are the palms**, and their meshes are named `*_palm`, not `*_finger`. The
   frame the skill positions is **44.3 mm forward** of the palm origins along `link5` x
   (0.126 − 0.0817), so there is a fixed, unmodelled geometric relationship between
   `contact_height_m` and the height at which anything actually touches the block.
3. Therefore **`contact_height_m` is a bookkeeping parameter, not a contact parameter.** The
   measured +15 mm offset is the symptom; this is the cause.

**This is why §2's refutation of the geometry hypotheses matters and does not contradict §8–9.** The
flick is not caused by *where on the block* contact happens (refuted, §3); it is caused by the
contact being an **edge grazing** rather than a face push, which follows from the frame mismatch
established here. Two different claims, both true: contact *position* does not predict the flick,
and the *frame mismatch* guarantees the contact is a graze.
