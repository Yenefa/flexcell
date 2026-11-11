# T08: the uncontrolled variable is ACHIEVED HEIGHT, not attitude. Pre-registered test.

**Date** 2026-11-12 · **n = 3 (seeds 5000, 5001, 5005 — spent instances)** · **PRE-REGISTERED before the run**

---

## 1. I refuted my own round-10 hypothesis first

Round 10 concluded the push variance came from an uncontrolled variable — the tool attitude, which
`move_to_pose.jsonl` shows varying by up to 1.02 rad. **That was wrong, and I checked it before building on it.**

Comparing the **reached orientation across separate runs at byte-identical commanded poses**:

| commanded x | runs | max attitude difference |
| --- | --- | --- |
| 0.1425 | 4 | **4.5°** |
| 0.1615 | 5 | 2.5° |
| 0.1805 | 5 | 3.7° |
| 0.1995 | 5 | 3.5° |
| 0.2575 | 10 | 3.4° |
| 0.2675 | 10 | 22.0° (the pre-push standoff only) |

**The attitude is repeatable to 1.4–4.5°.** The 0.44–1.02 rad `orientation_error_rad` is the error against the
*requested identity* orientation — a systematic offset, applied consistently — not run-to-run scatter.
**So attitude is not the uncontrolled variable, and my round-10 explanation is withdrawn.**

## 2. What actually varies

Across 11 usable runs the **block starts at exactly `[0.22, 0.0, 0.0175]` every time** — zero variance.
The attitude is repeatable. What varies is the **achieved end-effector height**:

```
achieved z across runs : 0.0198 – 0.0249   (about 5 mm of scatter)
commanded z            : 0.0175 everywhere
offset                 : +0.002 to +0.007
```

And the committed height sweep says the push outcome is extremely sensitive right there:

```
achieved (sweep commanded + ~0.004)   displacement
  0.0215                                151.14 mm
  0.0240                                 69.92 mm
  0.0265                                  6.32 mm
```

**The run-to-run height scatter straddles the cliff.** That is a quantitative mechanism with no free
parameter: 5 mm of scatter across a cliff about 2.5 mm wide explains the whole 0–131 mm displacement range.

## 3. Pre-registration

**One field changes:** `contact_height_m` 0.0175 → **0.0100**. `overdrive_m` stays 0.030. Instances: 5000, 5001,
5005 (one backwards, one success, one short — deliberately the three different outcomes).

**Reasoning.** If achieved ≈ commanded + 0.004, commanding 0.010 should achieve ≈ **0.014**, which is 7 mm
below the 0.0215 that produced 151 mm — far enough that ±2.5 mm of scatter cannot reach the cliff at 0.024.

**Prediction (falsifiable):**

| quantity | predicted |
| --- | --- |
| achieved z (from `move_to_pose.jsonl`) | **0.012 – 0.018** |
| displacement, all 3 runs | **≥ 0.060 m** |
| direction cosine, all 3 runs | **≥ 0.90** |
| runs pushed backwards | **0** |

**Falsified if** any run displaces < 0.060 m, or the cosine drops below 0.90, or a run goes backwards.

**What this cannot be.** These three instances are **spent**. Even a clean pass is a **mechanism test on spent
data**, not generalisation. And `unmoved: target_box_b` remains **UNMEASURED**.

**If it fails, the conclusion is settled**: three request-field levers tested, and the fix is in the control
layer, which needs approval rather than a fourth sweep.

## 4. Result

See §5.
## 5. Result — falsified, and in a way that closes the avenue

All three runs: **`ec=30`, zero displacement, zero motion.**

| seed | outcome | ec | displacement |
| --- | --- | --- | --- |
| 5000 | 1 | 30 | 0.0000 |
| 5001 | 1 | 30 | 0.0000 |
| 5005 | 1 | 30 | 0.0000 |

**Prediction falsified (predicted ≥0.060 m and cosine ≥0.90 on all three).**

### 5.1 Why it failed, and it is not a harness fault

`move_to_pose.jsonl` for all three:

```
target = [0.2575, 0.0, 0.010]
outcome = POSE_NOT_REACHED        error_code = 30
ik_precheck.ok = True             ik_precheck.detail = 'IK solution found'
```

**IK finds a solution; the arm cannot execute it.** Commanding 4 mm lower than the working height puts the
pose outside what the arm can physically attain. So the achieved contact height **cannot be moved below the
cliff with a request field** — the reachable floor sits above it.

### 5.2 It also explains `seed5002`, which I had recorded as UNKNOWN

`seed5002` failed with `ec=30` on both earlier batches. Its `move_to_pose.jsonl`, in both:

```
target = [0.2575, 0.0, 0.0175]      <- the ordinary APPROACH pose, not the lowered one
outcome = FAILED                    error_code = 20
ik_precheck.ok = True               reached_pose = None
```

**The same approach pose that succeeds in four other runs fails here twice.** The world is identical in every
run (block measured at exactly `[0.22, 0.0, 0.0175]`, zero variance), so the difference is the **arm's prior
state**, which nothing controls.

**`seed5002` is therefore re-attributed from `UNKNOWN` to Control / kinematics — marginal reachability** — not
because I wanted a label, but because its own log now names the failure.

## 6. The complete picture, after three request-field attempts

| commanded z | outcome across runs |
| --- | --- |
| 0.0100 | `POSE_NOT_REACHED` — **3 / 3**, IK feasible, not attainable |
| 0.0175 | usually reached (achieved **0.0198 – 0.0249**), intermittently `ec=20` on the approach |

The push pose sits at the **edge of the arm's reachable envelope**. That produces both symptoms at once:

1. **Intermittent total failure** — the approach pose is sometimes not reached at all (`seed5002`, twice).
2. **Marginal contact** — when it is reached, the achieved height scatters over ~5 mm, and the sweep shows
   outcome sensitivity across a ~2.5 mm band at exactly that height (0.0215 → 151 mm, 0.0240 → 70 mm,
   0.0265 → 6 mm).

**So the variance is not a tuning problem at the top edge of the block; it is the arm operating at its reach
limit, where small state differences decide whether the tool arrives at all.**

## 7. Three request fields, three falsifications

| lever | prediction | result |
| --- | --- | --- |
| `contact_height_m` 0.0200 → 0.0175 (r8) | works | **1/1 on dev, then 2/6 fresh — not generalised** |
| `overdrive_m` 0.005 → 0.030 (r10) | ≥5/6 | **3/6 — falsified** |
| `contact_height_m` 0.0175 → 0.0100 (this) | ≥2/3 in band | **0/3, pose unreachable — falsified** |

**The request-field avenue is closed by measurement, not by assumption.** Every remaining lever is in the
control layer or the tool geometry, and both require **human approval** to change.

## 8. What this establishes, and at what level

| claim | level |
| --- | --- |
| T08's variance is caused by operation at the arm's reachable boundary | **measured** — `POSE_NOT_REACHED`, achieved-z scatter, identical worlds |
| the fix is not available through any request field | **three falsified predictions** |
| `seed5002` failure class | **Control / kinematics**, named by its own log |
| False Success across every T08 run this session | **0** |
| T08 skill-level on unseen | **0/6, unchanged** |
| generalisation | **not claimed** — spent instances, mechanism test only |

## 9. What a human decision would unblock

Two changes, neither of which I will make unilaterally:

1. **Control layer** — command an explicit tool orientation and a pose inside the reachable envelope, instead
   of `orientation_enforced: False` with a pose on the boundary. This is `contracts/push.py` / `push_server.py`,
   both frozen.
2. **Tool geometry** — a side-mounted probe would let the contact point be chosen rather than inherited from
   wrist attitude. This is a robot-description change.

Until one of those is approved, further sweeps will keep producing falsified predictions, and four is enough
to stop.
