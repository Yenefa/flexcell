# Fresh unseen T08 at the corrected contact height: a real generalisation test

**Date** 2026-11-12 · **n = 6 fresh instances (seeds 4000–4005)** · **PRE-REGISTERED before any run**

---

## 1. Why this run exists

Round 8 took one push at `contact_height_m = 0.0175` on **dev** `seed2000` and it satisfied all four
sub-clauses of the push criterion (displacement 0.1058 m, cosine 0.9991, Δz 0.1 mm, **7.2 mm from the zone
centre**). That is **Simulation Tested at n = 1 on a tuning instance**. It is not generalisation, and the
mission's ladder does not let me call it that.

The original unseen seeds 3000–3002 are also unusable for a claim: they were already run during the
evidence loop, and the mission forbids reintroducing a task used during development as independent
held-out data. **So the only honest route is instances that did not exist before the configuration was
fixed.**

### 1.1 A first set was thrown away before any run — and why

My first attempt (seeds 4000–4005) varied the **block** position. **I discarded it unrun** once I checked
`/home/ros/flexcell-p14/scripts/sim_profile.py`: it always spawns `target_box_a` at **(0.22, 0.0)**. It can
place `zone_2` but not an arbitrary box pose. So those six instances would have graded against a zone while
the simulator put the block somewhere else — the same instance-pose defect already recorded for five
existing specs.

**The fix is to vary what the simulator does not have to place: the zone.** The block stays where the
simulator actually puts it, and the zone moves.

`generate_fresh.py` then emitted six (seeds 5000–5005) and wrote `freeze_manifest.json` **before the first
run**. It refuses to regenerate if the manifest exists.

```
T08-push-seed5000  sha=b7c9563bf1d7547f   zone_x 0.14   required travel >= 0.030 (task min binds)
T08-push-seed5001  sha=5feefe1f5abd7fc9   zone_x 0.13   required travel >= 0.030
T08-push-seed5002  sha=bb26293744514834   zone_x 0.12   required travel >= 0.040
T08-push-seed5003  sha=bb0a2cebad6acad9   zone_x 0.11   required travel >= 0.050
T08-push-seed5004  sha=6e9793bad256e5a5   zone_x 0.10   required travel >= 0.060
T08-push-seed5005  sha=3a8ad1c8933315f0   zone_x 0.09   required travel >= 0.070
```

**Therefore the claim this can support is narrower than I first intended**: generalisation over **zone
placement**, not over block placement. I am stating that rather than letting "6 unseen instances" imply more
than it is.

## 2. Pre-registration

**Protocol — identical to the recorded evidence loop except one field:**

| field | evidence loop | this run |
| --- | --- | --- |
| `contact_height_m` | 0.0200 | **0.0175** |
| `overdrive_m` | default (0.05) | **0.005** |
| `distance_m` | 0.09 | 0.09 |
| direction | from spec `[-1, 0]` | from spec |
| instances | dev + spent unseen | **fresh 4000–4005** |

**Prediction (falsifiable):**

> At `contact_height_m = 0.0175` and `overdrive_m = 0.005`, **all 6 of 6** fresh instances satisfy **all
> four** sub-clauses of the push criterion (displacement in [0.030, 0.150] m, |Δz| ≤ 0.020 m, cosine ≥ 0.90,
> final pose within 0.060 m of the zone centre).

**Why all six and not "most":** round 8 measured a single push travelling **0.1058 m**. All six zones here
require between 0.030 and 0.070 m of travel and sit within 0.05 m of where a 0.1058 m push lands
(`0.22 − 0.1058 = 0.1142`). So the predicted margin is large for every instance and a partial pass would mean
**run-to-run variance**, not a geometry limit — which is exactly what I want to find out.

**Falsified if** fewer than 6 of 6 pass. Any miss is reported as a miss; I will not re-tune and re-run on the
same instances.

**Commitment against tuning after the fact.** If the prediction fails, the correct response is to report the
failure. Editing the instances, the heights or the request distance after seeing the results, and then
reporting a pass, would be the manufactured-success pattern the mission forbids. The manifest exists to make
that visible.

**Harness guard.** A missing `push_object` server is recorded `HARNESS_ERROR`, never as a zero-displacement
push.

**What this cannot measure.** The task also carries `unmoved: target_box_b`, and this runner measures only
the pushed object. So a pass here is a **push-clause pass**, not a whole-task pass — that clause is
**UNMEASURED**, and I am recording it as such rather than assuming the blue block stayed still because it
is geometrically far away.

## 3. Result

See §4, filled in after the run.
---

## 4. Result — the prediction is FALSIFIED at 2 of 6

All six instance hashes verified **INTACT** before grading. Every run produced a usable measurement (no
`HARNESS_ERROR`).

| instance | disp (m) | cos | Δz (m) | zone_d (m) | ALL4 |
| --- | --- | --- | --- | --- | --- |
| seed5000 | **0.0820** | 0.9999 | −0.00002 | 0.0023 | **PASS** |
| seed5001 | 0.0128 | 0.9288 | −0.00001 | 0.0783 | FAIL |
| seed5002 | **0.0000** | 0.0000 | 0.00000 | 0.1200 | FAIL |
| seed5003 | **0.1018** | 0.9998 | −0.00009 | 0.0085 | **PASS** |
| seed5004 | 0.0363 | 1.0000 | −0.00000 | 0.0838 | FAIL |
| seed5005 | 0.0413 | 1.0000 | −0.00001 | 0.0887 | FAIL |

```
instances graded                  : 6 of 6
satisfy ALL FOUR push sub-clauses : 2
pre-registered prediction         : 6 of 6
unmoved:target_box_b              : UNMEASURED
```

**2 of 6. I predicted 6 of 6 and I was wrong.**

## 5. What the failure actually shows — and it is more useful than a pass would have been

The commanded parameters were **identical in all six runs**: `contact_height_m = 0.0175`,
`overdrive_m = 0.005`, `distance_m = 0.09`, same direction. The measured displacements were:

```
0.0000   0.0128   0.0363   0.0413   0.0820   0.1018   metres
```

**A spread of 0 to 102 mm under one command.** The push is **not repeatable**.

That reframes round 8 completely. Round 8 measured a single push of 0.1058 m at this contact height and I
called it close to a prediction of 0.085–0.105 m. It was one sample from a distribution whose range I had
no idea of. **The correct reading of round 8 is now: one draw from a wide distribution, not a configuration
that works.**

### 5.1 So what did the contact-height change actually buy?

| | old height 0.0200 | new height 0.0175 |
| --- | --- | --- |
| observed displacements | 69.92, 10.40 mm (two samples) | 0, 12.8, 36.3, 41.3, 82.0, 101.8 mm (six) |
| maximum observed | 69.9 mm | **101.8 mm** |
| push clause satisfied | 0 of the recorded runs | **2 of 6 fresh** |

Lowering the contact point to the block's centre raises the *ceiling* — it is possible to move the block
the whole way — but it does not make the push reliable. **Contact is still lost in four of six runs**
(`ec=28`), and one run moved nothing at all (`ec=30`, `ERR_MOTION_FAILED`).

**So the contact height was necessary and not sufficient.** Rounds 6–7 were wrong that T08 was blocked by
reach; round 8 was over-read as a working configuration; **this round shows the remaining problem is
contact repeatability, which is a control problem, not a geometry one.**

## 6. Failure attribution for the six runs (mission §9 ten categories)

| instance | error | category | basis |
| --- | --- | --- | --- |
| 5000, 5003 | `ec=28/36` but task clause satisfied | **Control** — contact lost / overrun after the task was met | measured displacement + zone |
| 5001 | `ec=28`, 12.8 mm | **Control** — contact lost early | measured |
| 5002 | `ec=30 ERR_MOTION_FAILED`, 0 mm | **UNKNOWN** — one run only; a motion failure is not a contact finding | not investigated |
| 5004, 5005 | `ec=28`, 36–41 mm | **Control** — contact lost partway | measured |

`ec=30` on seed5002 is recorded **UNKNOWN** on purpose. A single zero-displacement motion failure could be
a control defect, a transient, or a harness fault; one sample cannot distinguish them, and calling it
"control" would be the label-for-cause substitution this project has already made six times.

## 7. What this changes in the capability ledger

| claim | before this round | after |
| --- | --- | --- |
| T08 push clause satisfied at the corrected height | **"1/1 on dev"** (round 8) | **2/6 on fresh unseen = 33 %** |
| the round-8 configuration works | asserted | **REFUTED — it works sometimes** |
| T08 blocker | reach (r6–7), then solved (r8) | **contact repeatability** |
| T08 skill-level | 0/6 | **0/6, unchanged** — the skill certified nothing on any of the six |
| evidence level for the contact-height configuration | Simulation Tested | **Simulation Tested, 2/6, not generalised** |

**No generalisation claim is made.** The prediction was falsified, the instances are spent, and re-tuning on
them and re-running would be the manufactured-success pattern the manifest exists to prevent.

## 8. The honest next step

The measurement to make next is **repeatability**, not height: run the same frozen instance N times at
`contact_height_m = 0.0175` and measure the displacement distribution. If contact loss is the mechanism, the
distribution should be bimodal with a low mode near 10–40 mm. That is a control question, and it is where
the remaining capability actually lives.
