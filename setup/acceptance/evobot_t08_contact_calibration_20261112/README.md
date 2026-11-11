# Inverse contact-height calibration: no commanded height reaches the block face

**Date** 2026-11-12 · **Lane** sim-push · **Task** task-9
**Setup** `run_batch_v2.sh` (unmodified), single-shot arm, dev seed2000, 1 attempt, guard 0.140,
varying ONLY `contact_height_m`. Six heights, n=1 each. Zero orphans, lock released.

**Conclusion: (B), with a mechanism that is not the one either of us expected.**

No commanded height produces face contact. But the reason is not "the finger cannot reach the
face". It is that **the arm cannot descend to the commanded height at all when that height is
below the block top** — the descending finger lands on the block, the approach converges to the
block top instead of the target, and the push is refused before it starts. Four of the six
heights therefore never executed a push. Their contact logs are real, but they are the record of
a descent, not of a push.

---

## 1. The table

```
arm        cmd_h_m  first_z_m  x_offset_m  contact?   push_ran  world_disp_mm   cos   passed
H0200       0.0200     0.0350     -0.0013      yes        YES         144.13    0.9999   True
H0150       0.0150     0.0350     +0.0178      yes        YES          71.10   -0.9976   False
H0100       0.0100     0.0350     +0.0018      yes         NO           4.69    1.0000   False
H0050       0.0050     0.0350     +0.0069      yes         NO           4.43    0.9419   False
H0000       0.0000     0.0350     +0.0071      yes         NO           5.77    0.9836   False
HM0050     -0.0050     0.0350     +0.0082      yes         NO           5.89    0.8485   False
```

**First-contact z is 0.0350 at every one of the six heights**, over a 25 mm command range.
Linear fit: `first_z = 0.0001 * cmd_h + 0.0350`. The slope is 0.0001, not 1.0.

The block is a 35 mm cube resting on the table: it spans z = 0.0000 to 0.0350, centre 0.0175.
So first contact is always exactly the **block top**, which is the Lead's finding, confirmed at
six points instead of two.

Block centre is 0.0175. Every point is 17.5 mm above it. **Zero of six are within the 5 mm
tolerance of the centre.**

---

## 2. What I disagree with, and why it matters

The Lead's reading is that first contact is a property of the approach path — the arm descends
through the block-top region on the way to its target, so it touches the top no matter where it
is heading. **The first-contact result is exactly that and I confirm it 6/6.**

But the *explanation of the low-height runs* is not what the numbers say, and the difference
changes the recommended fix.

**Four of the six heights never pushed.** `push_00.json` records `increments_executed = 0`,
`contact_made = false`, `error_code = 30` (ERR_MOTION_FAILED) for H0100, H0050, H0000 and
HM0050. The driver log shows `moved 0.0000 m ... contact=False carry=False` in each. Those runs
recorded contact in the contact log — 25k to 27k contact points — but that contact is the
**descent landing on the block**, before the approach check failed. No push increment was ever
commanded.

So their "displacement" of 4.4 to 5.9 mm is not a push result. It is the block being nudged by
the arm coming down on it, measured between the bundle's start and end poses. The Lead's item 4
asked for H0000 to be recorded this way; the same applies to three more points that were not
flagged.

**The arithmetic of the failure is the real finding:**

```
arm       cmd_h    approach pos error    cmd_h + error
H0100    +0.0100        0.0235              0.0335
H0050    +0.0050        0.0289              0.0339
H0000    +0.0000        0.0346              0.0346
HM0050   -0.0050        0.0399              0.0349
```

In all four, `cmd_h + pos_error` lands between 0.0335 and 0.0349 — the block top (0.0350). The
arm descends, the finger meets the block's top face, and **the arm stops there**. The approach
target is below the block, so the measured pose is short of the target by exactly the amount the
command went below the top, and the approach gate rejects it at 0.020 m tolerance.

That is a *collision-limited* failure, not a *reach* failure. The arm is physically stopped by
the block it is trying to get under. This is why lowering the command does not lower the contact:
the contact is what prevents the descent.

### Consequence for the recommended fix

The Lead's conclusion — "the fix must be a link with collision geometry at the right height, or a
single-finger push" — is right, but for a sharper reason than "the parameter cannot reach the
face". The parameter is not merely ineffective; **below the block top it is unreachable, because
the finger cannot pass through the block.** A geometry change is needed not to position the
contact better but to make the commanded height physically attainable at all.

---

## 3. On the Lead's inversion claim — I partly disagree

The Lead's item 2 asks whether H0150's backwards flick is caused by face engagement. **My data
says the deep contact is not face engagement.**

Measuring each contact point against the block's own pose in the same record:

| arm | contact z range | block z (centre) during contact | contact z relative to block top |
|---|---|---|---|
| H0200 | 0.0324 – 0.0356 | 0.0164 – 0.0178 (did not rise) | **−1.5 mm to +0.6 mm** |
| H0150 | 0.0097 – 0.0784 | 0.0142 – 0.0175 (did not rise) | **−24.3 mm to +43.4 mm** |

H0200's contact is pinned to the top face within ±1.5 mm for the whole run — a pure edge drag,
exactly as described, and it is the trial that passed with 144 mm.

H0150's contact spans **68 mm of z**, from 24 mm *below* the block top to 43 mm *above* it. A
contact that goes above the block top is not on the block's face; the block is 35 mm tall and its
top is the highest thing there. The range is consistent with the block **rotating and being
lifted/tumbled** while the finger is in it, not with a stable palm-on-face push. Its z also dips
below the block's own bottom-referenced centre, which a face contact at mid-height cannot do
while the block stays flat on the table.

So I would not read H0150 as "most face engagement gives the worst outcome". I would read it as
"the block got tumbling contact and was thrown backwards". The Lead's intuition that face
engagement is not automatically better may still be right — but this trial does not demonstrate
it, because it is not a face push.

**With n=1 per height I claim only the first-contact result.** I agree with the Lead's item 3 and
go further: the displacement ordering across these six points is not interpretable at all, since
four of them are not pushes.

---

## 4. The falsified prediction, stated plainly

The Lead pre-registered (commit `1d8783b6`) a slope-1.0 model: first-contact z tracks the
commanded height, so a command near 0.0000 puts contact within 5 mm of the block centre, and the
falsification condition was that contact z at commanded 0.0000 must be within ±5 mm of 0.0149.

Measured: commanded 0.0000 → first-contact z **0.0350**. That is 20.1 mm from 0.0149, four times
the stated tolerance. **The prediction is falsified**, and the observed slope (0.0001) is four
orders of magnitude from the predicted 1.0.

I am recording this as a falsification, not as a revised story. The model that replaces it is not
"slope is smaller" but "the descent is collision-limited at the block top", which is a different
kind of claim: it says the commanded height never becomes the contact height because the block
intervenes, and it predicts the approach-error arithmetic in section 2.

---

## 5. What is firm and what is not

**Firm:**
* First-contact z = 0.0350 at all six commanded heights, spanning 0.0200 down to −0.0050. Slope
  0.0001. Six independent Gazebo runs, 6/6 identical to 0.1 mm.
* Four of six runs executed zero push increments (`increments_executed=0`, `contact_made=false`,
  `error_code=30`), and their approach error satisfies `cmd_h + error ≈ 0.0345`.
* H0200 contact stays within ±1.5 mm of the block top for the whole run.

**Not firm, and not claimed:**
* Any ranking of heights by displacement. n=1 per point, and four points are not pushes.
* Any claim that face contact is worse or better than edge drag. H0150 is not established to be
  a face contact.
* Any claim about what a geometry fix would achieve. That needs a modified robot model, which is
  outside this task's rules.

---

## 6. Rules compliance

* No threshold, limit or frozen file changed. `push.py`, `sim_profile.py`, `verify.py`,
  `evaluate.py` and all task specs untouched — the driver records their sha256 in each
  `manifest.txt`, and they match the round-2 freeze.
* All six bundles kept verbatim. Nothing hand-patched.
* `terminal_passed` and `passed` are separate columns in the table; H0200 is the only
  `passed=true`, and per section 2 it is an edge drag that overshot.
* No model calls, no paid APIs.
* One Gazebo at a time under `flock`, with a `pgrep` refuse-check per trial. Zero orphans after
  every trial; lock free at the end.
* Write scope: this directory only.
* H0000's contact log is real and kept, recorded as a real observation with its reason
  (`error_code=30`, approach failed) rather than discarded — as instructed.

## 7. Reproduce

```bash
bash setup/acceptance/evobot_t08_contact_calibration_20261112/run_sweep.sh
python3 setup/acceptance/evobot_t08_contact_calibration_20261112/analyse_contact.py runs
```

`analyse_contact.py` reproduces the Lead's round-1 numbers exactly when pointed at the round-2
evidence tree (0.0348–0.0350 at commanded 0.0200, offset 0.0148–0.0150), which is the check that
the first-contact extractor is the same measurement.

## 8. Files

```
run_sweep.sh          loops run_batch_v2.sh once per height, one lock per run
analyse_contact.py    first-contact z / x-offset / slope, plus the frame check
runs/H0200/ ...       one full evidence bundle + logs per height
```
