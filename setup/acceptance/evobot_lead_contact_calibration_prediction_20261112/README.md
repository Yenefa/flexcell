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

## The prediction said

> first-contact z should track the command with **slope 1.0**, and a command near 0.0000 should put
> contact within 5 mm of the block centre (0.0175). **Falsification criterion: contact z at commanded
> 0.0000 must be within ±5 mm of 0.0149.**

## What happened

**First-contact z is 0.0349–0.0350 at every commanded height from 0.0000 to 0.0200.** A 20 mm change in
the command moved the first contact by **0.1 mm**. My falsification criterion is met: at commanded
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
