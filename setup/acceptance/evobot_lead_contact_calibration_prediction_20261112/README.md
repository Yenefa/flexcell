# Pre-registration: what the contact-height sweep must show if the mechanism is understood

**Written 2026-11-12, BEFORE the sweep results exist.** The sweep is running in
`evobot_t08_contact_calibration_20261112/` (task-9, simulation lane). This file fixes the
prediction and the falsification criterion in advance so the result cannot be fitted afterwards.

---

## 1. The mechanism as currently measured

| Fact | Value | Source |
| --- | --- | --- |
| commanded `contact_height_m` | 0.0200 | task invocation |
| **measured first-contact z** | **0.0349 – 0.0350** | 10 dev trials, contact logs |
| block top | 0.0350 | 35 mm block on the table |
| implied finger-to-EE-frame offset | **+0.0149 m** | 0.0349 − 0.0200 |
| `end_effector_link` collision geometry | **none** | round 1 tooling finding |

`push.py:215-219, 408-414` computes the whole push path at **constant z = `contact_height_m`** and
applies it to the `end_effector_link` frame. Because that frame carries no collision geometry, the
bodies that actually touch are the finger links, which sit **above** the frame.

So at the default command the finger's lowest surface is at 0.0200 + 0.0149 = **0.0349**, which is
**exactly the block's top surface**. The skill has been performing a grazing top-edge contact by
construction — not by tuning.

## 2. Prediction (falsifiable)

If the finger is rigidly offset above the commanded frame and the push path is at constant z, then
contact height should track the command **with slope 1.0**:

| commanded height | **predicted first-contact z** | predicted contact character |
| --- | --- | --- |
| 0.0200 | 0.0349 | top edge (already measured) |
| 0.0150 | 0.0299 | upper face, near the top |
| 0.0100 | 0.0249 | upper face |
| 0.0050 | 0.0199 | **near block centre (0.0175) — face push** |
| 0.0000 | 0.0149 | mid face, **the target regime** |
| −0.0050 | 0.0099 | lower face |

**Specifically: a commanded height in the range −0.003 to +0.003 should put contact within 5 mm of
the block centre (0.0175), i.e. produce a genuine face push.** The x offset at first contact should
move from ≈ +0.017 (top far edge, what all ten dev trials show) toward **0.000** and then negative.

## 3. What would falsify this

| Observation | What it would mean |
| --- | --- |
| contact z stays ≈ 0.035 for **every** commanded height | the finger does **not** track the frame; the constant-z path is not what determines contact, and the parameter cannot reach the face. **Mechanism wrong** — and then the fix must be geometry (a link with collision at the right height, or a single-finger push), not a number. |
| contact z changes but **not** with slope ≈ 1 | the offset is not rigid; there is compliance or a trajectory that is not constant-z. Slope must be reported, not assumed. |
| contact disappears below some height | the arm cannot reach that low without hitting the table; record as `contact_established=false`, and that height bounds the achievable regime from below. |
| contact z tracks the command but the block is still flicked backwards | **contact height was never the cause**, and the round-2 refutation of the geometry hypothesis extends further than we thought. |

## 4. Why this is worth writing down first

The project's most expensive recurring error is not a wrong measurement, it is a **right measurement
fitted to a story afterwards**. Round 1 described the flick as "the effector cannot hold a contact
face" and it took a round to disprove. If this sweep lands on slope 1.0 with contact near 0.0175, it
is a mechanism confirmation; if it lands on anything else, the mechanism above is wrong and that must
be visible as a contradiction rather than absorbed into a slightly different narrative.

**The falsification criterion is: contact z at commanded 0.0000 must be within ±5 mm of 0.0149.**
Outside that, the rigid-offset model is wrong regardless of how plausible the rest looks.

## 5. Independent check to run on the lane's numbers

The lane measures first-contact z from its own logs. I will re-derive it from
`logs/contact_steps.jsonl.gz` with `evobot_lead_contact_mechanism_20261112/contact_first_touch.py`
and compare. **A first-contact z that I cannot reproduce from the raw log is not a result.**

---

# RESULT: the prediction is FALSIFIED

**Measured 2026-11-12, from the sweep's own contact logs, before reading the lane's write-up.**

## The numbers

| sweep point | commanded `contact_height_m` | **first-contact z** | contact z median | contact z range | x offset (median) | displacement | cos | passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H0000 | 0.0000 | **0.0350** | 0.0292 | 0.0176–0.0350 | +0.0084 | 5.77 mm | 0.984 | no |
| H0050 | 0.0050 | **0.0350** | 0.0289 | 0.0181–0.0350 | +0.0143 | 4.43 mm | 0.942 | no |
| H0100 | 0.0100 | **0.0350** | 0.0286 | 0.0246–0.0350 | −0.0034 | 4.69 mm | 1.000 | no |
| H0150 | 0.0150 | **0.0350** | 0.0157 | 0.0097–0.0784 | −0.0033 | 71.1 mm | **−0.998** | no |
| H0200 | 0.0200 | **0.0350** | 0.0345 | 0.0324–0.0356 | +0.0170 | **144.13 mm** | 1.000 | **yes** |
| HM0050 | **−0.0050** | **0.0350** | 0.0283 | 0.0161–0.0350 | +0.0077 | 5.89 mm | 0.849 | no |

## The prediction said

> first-contact z should track the command with **slope 1.0**, and a command near 0.0000 should put
> contact within 5 mm of the block centre (0.0175). **Falsification criterion: contact z at commanded
> 0.0000 must be within ±5 mm of 0.0149.**

## What happened

**First-contact z is 0.0350 at every commanded height from −0.0050 to +0.0200** — a 25 mm span of
commands, **six points, six identical first contacts to 0.1 mm.** My falsification criterion is met: at commanded
0.0000 the contact z is 0.0350, which is **20 mm** away from the predicted 0.0149 — four times the
±5 mm tolerance.

**The rigid-offset, slope-1.0 model is wrong.** `contact_height_m` does not translate the contact
point, and there is no commanded value in this range that puts the contact at block centre on first
touch.

## Why it is wrong — the descent, not the push

The EE is commanded **directly to the approach pose** at the contact height:

```
H0050: request t08loop-target_box_a-0 -> target [0.2575, 0, 0.005]     (ONE request)
H0200: request ... -> [0.2575, 0, 0.02], then [0.2095,0,0.02], ...      (approach + increments)
```

The arm travels from wherever it was to that pose, **passing through the block-top region on the way**.
The palms are wider than the block and the block top is at 0.0350, so the **first** thing any
descending approach touches is the block's top edge — regardless of the z it is heading for. First
contact is therefore a property of the **approach path**, not of the target height.

## What IS sensitive to the command — and it inverts the intuition

Contact z **after** first touch does depend on the command, and the dependence is the opposite of
what a "lower is better" story would predict:

| commanded height | contact z behaviour after first touch | outcome |
| --- | --- | --- |
| 0.0200 | stays at **0.0345–0.0350** — pure top-edge drag the whole way | **144 mm forward, PASSES** |
| 0.0100 | descends 0.0350 → **0.0267** — the palm slides down the face | 4.69 mm, stalls |
| 0.0050 | descends 0.0350 → **0.0241** | 4.43 mm, stalls |
| 0.0150 | drops to **0.0131–0.0145** — deepest face contact of all | **71 mm, and cos −0.998: flicked BACKWARDS** |

**The lowest contact (deepest face engagement) produced the worst outcome, and the highest contact
(edge drag) produced the only pass.** So "make it a face push" is not obviously the fix — the one
configuration that engages the face most is the one that flicks the block backwards.

This is consistent with §3's refutation from the other direction: contact **position** does not
predict the flick, and now we know **moving the contact lower does not help either**. The 0.0150 point
is the clearest evidence yet that the flick is a dynamic instability of the contact, not a matter of
where the contact sits.

## What this costs and what it buys

- **Costs:** the tidy "the parameter is wrong, calibrate it" story is dead. It would have been a
  satisfying round and it is not true.
- **Buys:** the parameter is now known to be **ineffective over its whole useful range** for its
  stated purpose, which is a stronger and more decision-relevant statement than "mis-calibrated".
  It also kills the proposed fix in the round-3 plan ("find the height whose contact z is 0.0175"),
  because no such height exists in the tested range.

## Honest limits

- **n = 1 per height.** Five points, one trial each, one instance. No variance estimate, and the
  displacement spread at neighbouring heights (4.43 vs 4.69 vs 71.1 vs 144.1 mm) shows this task is
  highly variable. Treat the *ordering* as indicative and only the *first-contact z* result as firm —
  that one is 5/5 identical to 0.1 mm and cannot be explained by noise.
- **H0000's push aborted** (`ec=30`, approach failed: measured pose 0.0346 m from target, tolerance
  0.020 m). Its contact log still shows contact because the descent touched the block before the
  approach check failed. Recorded, not discarded.
- The sweep may add points after this was written; if it does, this section gets a revision rather
  than a quiet edit.

## Addendum: the sweep finished with a sixth point below zero

`HM0050` (commanded **−0.0050**) also gives first-contact z **0.0350**. So the result covers a 25 mm
span of commanded heights, six points, six identical first contacts.

That completes the falsification with more force than the five points already had: there is no
monotone trend, no threshold, and no height in the tested range at which the first touch happens
anywhere other than the block's top surface.

### One more pattern worth recording, with the same caveat

| commanded | displacement | cos | passed |
| --- | --- | --- | --- |
| −0.0050 | 5.89 mm | 0.849 | no |
| 0.0000 | 5.77 mm | 0.984 | no |
| 0.0050 | 4.43 mm | 0.942 | no |
| 0.0100 | 4.69 mm | 1.000 | no |
| 0.0150 | 71.10 mm | **−0.998** | no |
| 0.0200 | **144.13 mm** | 1.000 | **yes** |

Four of six heights move the block only 4–6 mm — a **stall**, not a push — and the only height that
moves it far is the **highest** one, which is the pure top-edge drag. The one intermediate height that
engaged the face most deeply flicked it backwards.

**Still n = 1 per height.** The stall-vs-push split at 0.0200 could be luck; the first-contact result
cannot be. I am recording the pattern because it is the third independent line of evidence that
**face engagement is not the fix**, not because it is established.
---

# SECOND CORRECTION: two of my readings were wrong, and the real mechanism is better

**The simulation lane checked my analysis against its own runs and found two errors. Both are real and both are corrected here.** I verified each independently from the artifacts before accepting it.

## Correction 1 — four of six heights never pushed at all

I wrote that four low heights "stall", implying they were push attempts that failed to move the block. **They were not push attempts.** The skill's own result fields:

| point | cmd | `increments_executed` | `contact_made` | error |
| --- | --- | --- | --- | --- |
| H0000 | 0.0000 | **0** | false | 30 |
| H0050 | 0.0050 | **0** | false | 30 |
| H0100 | 0.0100 | **0** | false | 30 |
| HM0050 | −0.0050 | **0** | false | 30 |
| H0150 | 0.0150 | 2 | true | 28 |
| H0200 | 0.0200 | 5 | true | 36 |

Their 4.4–5.9 mm "displacements" are **the block being nudged by the arm descending onto it**, measured bundle-start to bundle-end. I had flagged exactly this for H0000 and failed to notice it applied to three more. So the spread I described as "four heights of varying push quality" is **two pushes and four descents**. My §"What IS sensitive to the command" table and its reading are withdrawn.

## Correction 2 — the mechanism is collision-limited, not merely ineffective

The approach errors carry the explanation. `cmd_h + pos_error`:

| point | cmd | approach error | cmd + error | block top |
| --- | --- | --- | --- | --- |
| H0000 | 0.0000 | 0.0346 | **0.0346** | 0.0350 |
| H0050 | 0.0050 | 0.0289 | **0.0339** | 0.0350 |
| H0100 | 0.0100 | 0.0235 | **0.0335** | 0.0350 |
| HM0050 | −0.0050 | 0.0399 | **0.0349** | 0.0350 |

**Four independent runs converge on 0.0335–0.0349 — a 1.4 mm span, all within 1.5 mm of the block top.** The finger descends, lands on the block's top face, and the arm **stops there**. The target is below the block, so the measured pose falls short by exactly the amount the command went below the top, and the approach gate rejects it at its 0.020 m tolerance.

**This is a collision-limited failure, not a reach failure.** The arm is physically stopped by the block it is trying to get under. That is why lowering the command cannot lower the contact: **the contact is what prevents the descent.** My conclusion (geometry fix, not a number) survives, but for a sharper reason than I gave — below the block top the command is not merely ineffective, it is **unreachable**.

## Correction 3 — H0150 is not face engagement

I read H0150's deep contact as "the most face engagement gave the worst outcome" and used it as evidence that face engagement is not the fix. The lane measured contact against **the block's own pose in the same record**:

| point | contact z | relative to block top | reading |
| --- | --- | --- | --- |
| H0200 | 0.0324–0.0356 | **−1.5 mm to +0.6 mm** | pinned to the top face — a pure edge drag |
| H0150 | 0.0097–0.0784 | **−24.3 mm to +43.4 mm** | spans 68 mm, reaching 43 mm **above** the block top, where there is only air |

A contact reaching 43 mm above a 35 mm block is not on the block's face. **H0150 is tumbling/rotating contact, not a palm-on-face push**, and it must not be recorded as evidence that face engagement backfires. My broader claim that "face engagement is not automatically better" may still be true, but **this trial does not demonstrate it and I withdraw it as support**.

## What survives, and it is now firmer

| Claim | Status |
| --- | --- |
| First-contact z = 0.0350 at all six commanded heights, −0.0050 to +0.0200 | **FIRM** — 6/6, 0.1 mm spread; fitted slope 0.0001 against a predicted 1.0 |
| My pre-registered prediction is falsified | **FIRM** — missed by 20.1 mm, 4× its own tolerance |
| The command is **unreachable** below the block top | **FIRM** — four independent runs converge on the block top within 1.5 mm |
| The contact frame is the **world** frame | **FIRM** — contact reads 0.0350 (block top) not +0.0175 (local half-height). I had listed this as an unproven assumption; the lane proved it |
| "four heights stall" | **WITHDRAWN** — they never pushed |
| "H0150 = deepest face engagement, worst outcome" | **WITHDRAWN** — it is tumbling contact |
| Any displacement ordering across heights | **NOT INTERPRETABLE** — n=1, and four of six are descents |

## The fix this implies, stated more sharply than before

Not "calibrate the height" and not even "the parameter is ineffective". The push skill cannot get its finger **under** the block's top face at all, because the block is in the way. A face push requires either:

- a **different contact body** — something that can reach the face without descending through the top, e.g. a side-mounted pusher or a single finger entering from the side; or
- an **approach from the side** rather than from above, so the finger never has to pass through the block's footprint.

Both are geometry changes to the robot or the motion, not parameter changes. **This is now a well-supported negative result about the skill's design, which is worth more than the calibration number I set out to find.**

## Note on the discipline that caught this

Three of my claims were corrected this round by measurement — the pre-registered prediction, the stall reading, and the H0150 reading — and two of the three were caught by a lane checking my analysis against the same artifacts. Recording them in order, with the original text left in place, is the only way the correction is worth anything.
