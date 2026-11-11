# Independent check of the place-release-predicate refutation

**Auditor** gate-auditor · **Date** 2026-11-12 · **Verdict on both requests: CONFIRMED, with one correction and one addition that strengthens the finding.**

Sources: `evobot_crosstype_20261111/runs_T14_ordered_pair/` (B) and
`evobot_p0_aprime_execution_20261112/runs/` (A-prime, my own 16 executions).
No file under the Lead's diagnosis doc was modified.

---

## Q1. Is "recovery from this defect" the right reading? — YES, and it is worse than that

The Lead's reading is correct. My addition: on both runs the first attempt had **already
released the box at its destination**, so the retry was *redundant work*, not a rescue.

### The resume is a full-stage re-execution, not a checkpoint replay

`HO-2efba46248da`, `sim/skills/pick.jsonl`:

```
[0] target_box_a  outcome=0  picked target_box_a: attached, measured rise 0.102m   <- attempt 1
[1] target_box_a  outcome=0  picked target_box_a: attached, measured rise 0.104m   <- attempt 2, RE-PICKED
[2] target_box_b  outcome=0  picked target_box_b: attached, measured rise 0.094m
```

The object is picked **twice**. A checkpoint/partial resume would continue from the
failed place; this re-runs PICK and PLACE for the whole stage.

The composite logs agree — attempt 2 (`composite-aad6efd9d3a346ae.jsonl`) opens with
`PLAN` → `OBSERVATION target_box_a-0` → `STARTED target_box_a-0`, the same stage attempt 1
started, from the beginning.

Caveat I checked and rejected: attempt 1 had `completed_stage_ids=[]`, so a checkpoint
resume would *also* start at stage 0 and the two would be indistinguishable from the
composite log alone. **The double pick is what distinguishes them** — it proves full
stage re-execution.

### Attempt 1 had already put the box where it needed to be

`HO-2efba46248da`, carried pin targets and intended plan:

```
intended:  target_box_a -> [0.205, 0.050]
           target_box_b -> [0.295, 0.050]

after attempt-1 release:  target_box_a pinned at [0.207, 0.046]  = 44 mm from zone_2 centre
final ground truth:       target_box_a [0.201, 0.055] @ 49 mm
                          target_box_b [0.287, 0.044] @ 37 mm   both inside the bin
```

Timeline from `carry.jsonl`:

```
row 73  stop  cause=release  object=target_box_a  engaged=true   <- box released AT destination
row 74  stop  cause=replace                                     <- 8.2 s later
row 75  pin   object=target_box_a  target=[0.207, 0.046]
row 76  start object=target_box_a                               <- retry picks it back up
```

So the reward for the retry was: pick the box up out of the correct destination and put
it back 5–9 mm away. **The task was physically complete after attempt 1; the retry
re-did it.**

`HO-d3ab212142de` is the same shape (attempt-1 drop 38 mm from the bin centre).

### Why the retry "succeeded"

`place.jsonl` attempt 1: `gripper did not open (position=-0.011 requested=0.02 stalled=True)`,
`error_code 25`. Attempt 2: `released=true, err=0, drop error 0.007m`. The gripper opened
the second time. That is the same stochastic aperture failure resolving itself, not a
capability the first attempt lacked.

**Q1 verdict: the Lead's refutation stands.** There is no independent capability in the
resume path — it is a whole-stage retry, and in these two runs it retried a task that
was already done.

---

## Q2. Was the carry offset over-read? — NO, the mechanism is confirmed; the number needs 1.6 mm

`carry.jsonl` confirms the pin. Across all 16 B runs:

| probe | measured |
| --- | --- |
| `event: pin` records | **2642, all `confirmed: true`** |
| backends | `velocity_servo` — 102/102, single backend |
| `start` offsets with a z component | 34, z range **−169.5 … −154.9 mm**, mean **−162.1 mm** |
| gripper/object contact records in any skill log | **0** |

**Correction to the Lead's figure:** −163.8 mm is one specific `start` offset, not the
value. Measured across 34 start events the mean is **−162.1 mm** and the range spans
14.6 mm. The conclusion is unaffected — the object rides ~162 mm below the tool point,
far beyond finger reach — but the single number should not be quoted as *the* offset.

### The decisive argument does not depend on the offset at all

Contact records are an absence-of-evidence argument, which I do not want to lean on
alone. There is a causal test:

> **If the gripper were holding the box, a gripper that fails to open would retain it.**
> It does not. In 4 of my 7 failures the gripper stayed closed at −0.011 yet **both
> boxes were released and both reached the bin**.

Evidence: release counts per run (`carry.jsonl`, `cause=release`) vs the evaluation
outcome:

| A-prime run | place err25 | pin releases | evaluated |
| --- | --- | --- | --- |
| HO-4dbb21d087ae | 1 | **2** | **PASS** |
| HO-51600cf21179 | 1 | **2** | **PASS** |
| HO-675c07e900e7 | 1 | **2** | **PASS** |
| HO-da7c04bdece5 | 1 | **2** | **PASS** |
| HO-40348a081df6 | 1 | 1 | fail |
| HO-c79ebfe5c9e6 | 1 | 1 | fail |
| HO-dcf52d233154 | 1 | 1 | fail |

**The release count predicts the world state perfectly (7/7); the aperture verdict
predicts nothing.** Both boxes released ⇒ pass. One released ⇒ fail. The `place`
skill's release predicate is measuring a gripper that is not holding the object.

---

## Frequency: the Lead's numbers reproduce exactly

| | place attempts | err25 | rate |
| --- | --- | --- | --- |
| A-prime (my 16 runs) | 29 | 7 | **24.1%** |
| B (archived 16) | 34 | 5 | **14.7%** |
| **pooled** | **63** | **12** | **19.0%** |

The Lead reported 12/63 = 19%, A-prime 24.1%, B 14.7%. **Identical.**

---

## A trap I fell into while checking, recorded rather than hidden

My first pass appeared to show 4 of the 7 failures with `released=True, err=0` — i.e. a
*second* failure mode where `place` succeeded but the composite still reported error 62.

That was **my bug**. `place.jsonl` records `outcome` as the string `"0"` on success and
the integer `1` on failure. My filter `d.get("outcome") != 0` treats `"0" != 0` as True
in Python, so **every successful place row was classified as a failure**. Re-run with
`int(outcome)`, all 7 are `err=25` and there is no second mode.

Recorded because it is the same class of error as the `move_sequence` asymmetry in
`evobot_p0_aprime_execution_20261112/README.md` section 3: a comparison that silently
used two different recorders and manufactured a finding that was not in the world.

---

## What I could not verify

- **No physics-engine contact trace** for these runs. The claim "the fingers never touch
  the object" rests on: zero contact records in skill logs, a 162 mm stand-off, and the
  causal test above. The causal test is the strongest of the three and stands on its own.
- **The 51-of-539 historical figure** across 21 archives was not re-derived here — only
  the two live arms (63 attempts) were. I have no reason to doubt it and no evidence for
  it either way.
- **The other 5 of the 12** err25 attempts in B were not individually traced to a
  released/not-released outcome the way the 7 A-prime ones were.

---

## Bottom line

1. **Recovery refutation: CONFIRMED and understated.** The resume re-runs the whole
   stage, including re-picking. On both runs attempt 1 had already delivered the box to
   the bin; the retry duplicated completed work.
2. **Pin reading: CONFIRMED.** Mean z offset −162.1 mm (not −163.8 mm), 2642/2642 pins
   confirmed, zero contact records, and a causal test that does not rely on any of that.
3. **The aperture predicate is not merely miscalibrated — it is measuring the wrong
   physical quantity.** Aperture cannot report the state of an object the gripper is not
   holding. Six of the bundled gates in the T08 verifier share this pattern; this one is
   load-bearing for the task verdict itself.
