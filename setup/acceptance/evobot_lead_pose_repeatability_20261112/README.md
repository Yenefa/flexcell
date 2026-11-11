# The arm repeats to ±3.4 mm; the cliff it must land on is 2.5 mm wide

**Date** 2026-11-12 · **Zero Gazebo runs — measured from 3,426 archived successful moves**
**This is the mechanism behind three falsified request-field levers.**

---

## 1. The question

Three request-field changes were pre-registered and falsified (contact height down → 2/6; overdrive up → 3/6;
contact height far down → 0/3 `POSE_NOT_REACHED`). Three failures is a pattern, not bad luck, and I had been
explaining it with a 5 mm scatter measured on a handful of runs.

**3446 moves with both a commanded pose and an achieved pose are already archived.** So the question — how
repeatable is the arm at contact height? — was answerable without running anything.

## 2. The measurement

`move_to_pose.jsonl` records `target.position`, `reached_pose`, `outcome` and `position_error_m`. Across every
archive: **3,426 moves SUCCEEDED**, 20 were `POSE_NOT_REACHED`.

### All successful moves

| cmd z | n | achieved mean | mean dz | **sd dz** |
| --- | --- | --- | --- | --- |
| 0.0200 | 192 | 0.0238 | **+3.75 mm** | **3.43 mm** |
| 0.1775 | 535 | 0.1801 | +2.61 mm | 3.67 mm |
| 0.1895 | 546 | 0.1917 | +2.18 mm | 3.50 mm |
| 0.2375 | 536 | 0.2380 | +0.49 mm | 3.68 mm |
| 0.2775 | 534 | 0.2756 | −1.92 mm | 3.77 mm |
| 0.2895 | 1039 | 0.2888 | −0.74 mm | 3.73 mm |

**The systematic offset drifts with height (−1.9 mm to +3.8 mm), but the scatter is ~3.5 mm at every height.**
A height-dependent calibration could remove the drift and would still leave the scatter.

`position_error_m` over all 3,426 successes: **mean 6.53 mm, median 6.76 mm, p95 9.16 mm, max 19.43 mm**. And
`position_tolerance_m` accepts 20 mm — so the controller routinely operates near its own tolerance limit.

## 3. The number that settles P2's request-field avenue

At contact height (commanded z ≤ 0.06, **n = 197**):

```
achieved z:  mean 0.0237   sd 3.44 mm   min 0.0165   max 0.0369
spread (max - min): 20.37 mm
```

The committed height sweep brackets exactly this range:

| achieved-height band | displacement | share of 197 moves |
| --- | --- | --- |
| < 0.01875 | **151.14 mm** | 4 (2.0%) |
| 0.01875–0.02125 | **69.92 mm** | 29 (14.7%) |
| 0.02125–0.02375 | **6.32 mm** | 85 (43.1%) |
| 0.02375–0.02750 | **3.55 mm** | 51 (25.9%) |
| ≥ 0.02750 | **0.59 mm** | 28 (14.2%) |

So a single fixed command lands across **the entire behavioural range of the sweep**, from 151 mm to 0.6 mm.

**The cliff between the 69.92 mm and 6.32 mm cases is 2.5 mm wide. The arm repeats to ±3.4 mm, with a 20.4 mm
total spread. The scatter is roughly eight times the feature it must resolve.**

## 4. What this explains, and what it rules out

| observation | now explained |
| --- | --- |
| rounds 9 and 10 both scored about half the instances | the pass band is a minority of where the arm lands |
| round 8's single success was not reproduced | one draw from a 20 mm distribution |
| `contact_height_m = 0.0100` gave 3/3 `POSE_NOT_REACHED` | outside the achievable distribution entirely, not merely unlucky |
| round 10's "uncontrolled variable is attitude" | **wrong** — attitude is repeatable; *position* is not |

**A request-field change cannot fix this.** Not because the right value is unknown, but because there is no
value: for any fixed command the arm lands somewhere in a 20 mm distribution several times wider than the
behavioural feature. Choosing a different fixed command relocates the distribution; it does not narrow it.

That is the honest ending for the avenue I pursued over rounds 8–11, and it is a better ending than "three
attempts failed". **It is a capability limit of the position controller in this configuration, measured to
±0.1 mm on 197 samples.**

## 5. What would actually work, stated as requirements rather than wishes

1. **Reduce pose repeatability to well under 2.5 mm**, or
2. **Remove the cliff** — a contact strategy whose outcome is not a near-discontinuous function of depth, or
3. **Close the loop** — measure the achieved pose and act on it, instead of commanding a pose and hoping.

(3) is the one a robotics engineer would reach for first, and it is a control-layer change in
`contracts/push.py` / `push_server.py` — **both frozen**. Option 2 changes tool geometry. **Both need human
approval; neither is a parameter I can set.**

## 6. Why this is not a threshold argument

No threshold was lowered, and none is proposed. The sweep is unchanged; the evaluator is unchanged; the
criteria are unchanged. The claim is narrower than "the task is too hard": **the skill is being asked to
resolve a 2.5 mm feature with a 20 mm actuator distribution**, and the measurement says so with 197 samples
rather than an opinion.

## 7. Reproduce

```bash
python3 setup/acceptance/evobot_lead_pose_repeatability_20261112/analyse_repeatability.py
```

Reads every archived `move_to_pose.jsonl`, keeps `outcome == SUCCEEDED` with both a commanded and an achieved
pose, and prints the tables above. **No simulator, no model calls, no writes.**