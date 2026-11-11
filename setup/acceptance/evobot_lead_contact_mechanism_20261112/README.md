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
