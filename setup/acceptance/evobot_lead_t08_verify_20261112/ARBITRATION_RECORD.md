# ARBITRATION RECORD — human ruling on the gripper gate (2026-11-12)

**Authority**: direct human decision. This supersedes my `DECISION_NEEDED.md` request.
**Scope**: routing for the new calibration goal. **No threshold has been changed and none will be until
calibration completes.**

---

## 1. The ruling, verbatim in substance

| item | decision |
| --- | --- |
| `max_aperture_change_rad = 0.002` | **KEPT, frozen, historical version preserved** — no in-place edit |
| unit | **metres (m)**; the old field name is **wrong** |
| the known-valid push at 3.06 mm | **registered as a gate false-rejection counterexample** |
| new threshold | **NOT determined. Must be calibrated.** |
| old baseline hashes | **NOT re-pinned** |
| new baseline | **create v2**, stating the contract change and the re-run scope |
| P4 experience transfer | **`BLOCKED_ON_TASK_SUITE`** — no low-value paid calls |

## 2. The distinction the ruling draws, and it is the important part

> **A verifier false-rejection does not mean the robot failed the task.**

And:

> *"Prefer false rejection over admitting a false success"* is correct for a **safety gate's conservative
> decision**, but it **cannot be the final standard for research measurement**. If the threshold may be
> raised arbitrarily — or every action refused — False Success is trivially zero and **EvoBot has also lost
> the ability to complete tasks.** **So False Success and False Failure must be measured together.**

**Consequence for T08 that I must carry from now on**: the current gate may serve as a **conservative safety
constraint**, but **it may not be cited as evidence about the robot's pushing ability**. T08's recorded level
therefore drops from "Simulation Tested, n=2" to:

> **`CALIBRATION_UNSUPPORTED` — 2 gate-passing unseen instances, plus ≥2 known FALSE REJECTIONS of physically
> correct pushes. The gate, not the robot, is the open question.**

## 3. P0 — FROZEN markers, added without editing anything

| marker | applies to | meaning |
| --- | --- | --- |
| `CALIBRATION_UNSUPPORTED` | `max_aperture_change_rad = 0.002` | the bound has **no calibrated operating point** — independent audit found it bimodal, **no samples between 1.287 and 3.057**, and the bound sits ~**154× below** the observed pass-region value |
| `KNOWN_FALSE_REJECTION` | `U_shot/seed3001`, `U/seed3000` | both **passed the push clause** (144.0 mm and 121.7 mm, vertical **0.00000**, in zone) and were rejected on `gripper` alone (0.0035 / 0.0030 vs 0.0020) — finger deflection during contact, not a grasp |
| `UNIT_NAME_INCORRECT` | the field name `max_aperture_change_rad` | the gripper joints are **prismatic**; their joint positions are in **metres**, not radians. The name is wrong and the unit is `m` |

**Nothing was edited to add these.** The frozen version and all historical results are untouched; the markers
live in this record and in `FACT_STATE`.

## 4. What I will NOT do

- **Will not change 0.002.**
- **Will not re-pin the old baseline.**
- **Will not reverse-engineer a new threshold from the single 3.06 mm sample** — the ruling forbids it and it
  would be fitting a bound to one point.
- **Will not let the gate's conservatism be reported as the robot's capability, in either direction.**

## 5. Next: the calibration goal

`docs/EVOBOT_GRIPPER_CALIBRATION_GOAL_20261112.md` records the human-authored goal verbatim in structure:
**P0 freeze → P1 acquire (≥20 grasps, ≥20 valid pushes, ≥20 failures; varied contact height, position,
attitude) → P2 mechanism analysis (test whether aperture displacement separates at all; do not presuppose a
single threshold; consider composite criteria) → P3 independent validation on fresh seeds → P4 versioned
delivery.** Acceptance must report True/False Acceptance and Rejection, task success, False Success **and**
False Failure, with confidence intervals; any accepted wrong grasp or unconfirmed-contact-cleared-as-push
keeps its failure record and is refused promotion.

**Its stated final objective, which I am adopting as the standard**: *"not to find a number that passes more
experiments, but to establish a reliable criterion that distinguishes real physical behaviour."*

