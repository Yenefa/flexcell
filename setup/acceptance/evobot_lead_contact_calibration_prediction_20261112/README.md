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
