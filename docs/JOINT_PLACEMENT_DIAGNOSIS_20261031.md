# Why the joint backend lands ~2 mm off: it is the drop, not the carry

Status: diagnosed with two declared diagnostic runs on the local stack. This explains
the placement gap that [#80](https://github.com/Yenefa/flexcell/pull/80) measures and
corrects how the 12.252 mm outlier in that evidence should be read. D3 stays **NO_GO**.

## What was asked

In the five-task parity comparison the `detachable_joint` backend placed the box
2.16–2.25 mm from the target on single-object tasks and **12.252 mm** on the
dual-object demo, while `teleport` and `velocity_servo` stayed inside 0.23 mm. Two
questions: is the 12 mm systematic, and where does the error come from at all?

## Method

1. **Re-run the exact failing case** with the 2 ms physics trace declared
   (`manifest.json`, one `dual_object` episode, joint backend, MTC):
   `python3 scripts/sim_window.py --manifest .../manifest.json --backend detachable_joint --skill-backend mtc`.
2. **Decompose the trace** with `decompose.py`: per object it reports the release
   height above the target, the lateral error *at* the moment of release, the lateral
   speed at release, and where the box actually landed after the drop.
3. **Perturb the drop height** and see whether the error follows it
   (`manifest-clearance-50mm.json`, declared 50 mm release clearance instead of the
   default 12 mm).

The first attached frame of each session is ignored on purpose: the joint is created one
step earlier than the constraint settles, and a naive "first vs last" comparison reports
a 0.12 m drift that never happened. That mistake is exactly what the first draft of this
analysis made.

## Results

| run | object | release height | lateral error **at release** | lateral speed | landed error |
| --- | --- | --- | --- | --- | --- |
| 12 mm clearance | A | +12.47 mm | +0.11 / −0.04 mm | 1.6 mm/s | +1.32 / −1.71 mm |
| 12 mm clearance | B | +12.38 mm | −0.02 / −0.01 mm | 1.0 mm/s | +2.67 / +0.41 mm |
| 50 mm clearance | A | +50.03 mm | +0.01 / −0.00 mm | – | −2.26 / +3.15 mm |
| 50 mm clearance | B | +50.43 mm | +0.03 / +0.02 mm | – | **+9.43 / +1.45 mm** |

Three things follow.

1. **The carry is not the problem.** At release the box is within **0.11 mm** laterally
   of the target — the joint, the arm and the offset are all doing their job.
2. **The drop is the problem.** The box is released at the declared clearance above the
   target and then falls; the landing scatters it 1.3–2.7 mm at 12 mm clearance, and
   2.3–9.4 mm at 50 mm clearance. Four times the drop height, roughly two to four times
   the error.
3. **The 12.252 mm was a landing, not a mechanism of its own.** It sits inside the
   scatter distribution this experiment measures — the 50 mm run produced a 9.43 mm
   miss from one landing alone. One unlucky landing at 12 mm is not evidence of a
   different failure mode.

Why the legacy backends do not show it: `teleport` and `velocity_servo` move the **box**
to the commanded pose every step and release it there, so there is no free fall to land
from. The joint backend can only move the **arm**, so the release is necessarily a drop.

## What this changes

- The parity comparison in #80 should be read as: the joint backend is ~10x less
  accurate **because of landing scatter after a declared free fall**, not because the
  attachment or the following is loose. The 12.252 mm is one sample of that scatter.
- Any accuracy claim for this backend has to be stated against the release clearance it
  was measured with. A single "±2 mm" number would be wrong the moment the clearance
  changes.
- If the joint backend is ever brought closer to legacy accuracy, the lever is the
  release: lower clearance, or lower-and-release instead of drop. That is a behaviour
  change needing its own window and its own evidence — not something to assume.

## Still unknown

- Whether a smaller declared clearance (below 12 mm) reduces the error monotonically, or
  whether contact with the table before release introduces a new failure. Untested.
- The original 12.252 mm run declared **no** per-step trace (the parity manifest does not
  set `physics_step_s`), so that specific landing cannot be replayed. That is a defect in
  the window declaration, not in the backend: any window whose numbers will be cited
  should carry the trace.
- One diagnostic run per clearance. This is a mechanism demonstration, not a rate.

## Reproduce

```bash
python3 scripts/sim_window.py --manifest setup/acceptance/dual_object_diagnosis_20261031/manifest.json \
  --out /tmp/dual-12mm --backend detachable_joint --skill-backend mtc
python3 setup/acceptance/dual_object_diagnosis_20261031/decompose.py /tmp/dual-12mm/trial-01/run-*

python3 scripts/sim_window.py --manifest setup/acceptance/dual_object_diagnosis_20261031/manifest-clearance-50mm.json \
  --out /tmp/dual-50mm --backend detachable_joint --skill-backend mtc
python3 setup/acceptance/dual_object_diagnosis_20261031/decompose.py /tmp/dual-50mm/trial-01/run-*
```
