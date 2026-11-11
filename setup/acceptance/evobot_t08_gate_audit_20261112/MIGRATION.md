# MIGRATION to verify.py v1.1.0 / evaluate.py v0.6.0

**Author** gate-auditor · **Date** 2026-11-12 · **Status** PROPOSED, not applied

Why a version and not an edit: this project's discipline is that a changed
acceptance protocol becomes a new version and old results keep the version that
graded them. `evaluate_v0.3.0.FROZEN.py` was preserved exactly this way. Nothing
here is applied; `patches/` contains the proposed diffs.

---

## 1. What each patch fixes

| Patch | Finding | Change | Severity |
| --- | --- | --- | --- |
| `01-verify-v1.1.0-bind-rest.patch` | F1, F2 | `verify()` takes a `spec` and recomputes `rest_height_m` from `spec.objects[].initial_pose[2]`; a declared rest that disagrees is a hard fail | HIGH |
| `02-verify-v1.1.0-bind-run.patch` | F6, F7 | bundle must carry `task_sha256` matching the spec and a `run_id` the caller confirms; `execution_window` filters samples | HIGH |
| `03-verify-v1.1.0-digest.patch` | F3, F4, F5 | recompute `bundle_sha256`; require `manifest.files` completeness; cross-check `max_z_m` against the bundle's own samples | HIGH |
| `04-recorder-v1.1.0-gap.patch` | F10, F11 | `max_gap_ns` becomes a declared bound from the physics step period, not `max(observed)`; sample `seq` is the physics step, not the log index | MEDIUM |
| `05-verify-v1.1.0-gates.patch` | F8, F9, F12, F15 | gripper refuses n<2; `pusher_links` from an allow-list; `dropped_samples` read; `events` cross-checked | MEDIUM |
| `06-evaluate-v0.6.0-optin.patch` | — | `evaluate()` opts into v1.1.0 and adds a distinct `reason` for overshoot vs undershoot (F14) | MEDIUM |

## 2. Re-grading policy — which results change

| Result set | Version that graded it | Under v1.1.0 |
| --- | --- | --- |
| T01–T06 frozen results | evaluate.py ≤0.5.0, no evidence layer | **UNCHANGED.** No `push` clause, so no evidence requirement. |
| T08 results graded v0.5.0 / verify v1.0.0 with a bundle | v0.5.0 | **RE-GRADE.** A bundle whose `rest_height_m` disagrees with the spec becomes `passed=false` under v1.1.0 (it was already false if the producer was honest, but now it is provable). |
| T08 results with NO bundle | v0.5.0 | **UNCHANGED** (`passed=false` both ways). |
| Any historical `passed=true` on a push task | v0.5.0 | **MUST be re-graded before being quoted.** None exist this round. |

The re-grade is mechanical: `verify_v1.1.0.verify(bundle, terminal, limits, spec)`.

## 3. What v1.1.0 deliberately does NOT change

- The frozen numbers `0.03 / 0.15 / 0.02 / 0.9 / zone 0.06` stay in evaluate.py and
  are not touched by any patch.
- The 9 gate names and their order stay identical, so a diff of gate output is
  readable.
- `verify.py` v1.0.0 is left **byte-identical**; v1.1.0 is a new file.
- The gripper limit `0.002` is **NOT** changed by these patches. The units question
  (finding F18, `README.md`) is a threshold decision that changes what success
  means and needs human approval. It is called out separately.

## 4. F18 — gripper aperture bound: ADJUDICATED, no threshold change

Full analysis: `FINDING_F18_GRIPPER_CORRECTION.md`.

### 4.1 The units claim was wrong (retracted)

I initially reported `max_aperture_change_rad = 0.002` as a mm-to-radian error. That
was **wrong**: both gripper joints are **prismatic** in the URDF
(`gripper_left_joint`, `gripper_right_joint`; `<limit lower="-0.011" upper="0.02"/>`),
so a joint position is a linear displacement in **metres** and `0.002` really is
2 mm. Claim withdrawn.

### 4.2 What is genuinely wrong: the field name

`max_aperture_change_rad` carries **metres**; `verify.py:339` reports it as
`limit_rad` and the reason string says "rad". A label asserting a unit the quantity
does not have. **Severity LOW** — it cannot admit or reject a run by itself.
v1.1.0 renames it `max_aperture_change_m` / `limit_m`. No value change.

### 4.3 What the gate actually bounds, and what it cannot

The gate bounds **travel** (`max(span) - min(span)`), not absolute position:

| case | travel | vs 2 mm |
| --- | --- | --- |
| nominal grasp (open +0.020 -> closed ~-0.0013) | ~21.3 mm | 10.6x over — rejected |
| R/t1 push | 3.06 mm | 1.53x over — rejected |
| 937-sample calibration push | 0.0000010 m | accepted |

So the bound does separate a real grasp from R/t1. The Lead's point B compared
**absolute positions** (grasp -0.00107 vs R/t1 -0.00296); that is not the quantity the
gate measures, and it does not show the gate cannot separate the two.

The genuine hole is different: **the gate measures motion, never enclosure.** Fingers
already closed around an object, arm drags it => travel ~0 => gate passes. Not fixable
by changing the number; needs a different observable (finger contact force, or
object-relative pose).

### 4.4 R/t1 disposition — `passed=false` under BOTH versions

**Verdict: UNRESOLVED, not false rejection.** Only one genuine non-grasping push has
ever been measured (937-sample run, travel 0.0000010 m). A nominal grasp travels
~21.3 mm. R/t1's 3.06 mm is 3093x above the one non-grasp sample and 0.14x a nominal
grasp — inside an interval with no non-grasp measurements in it. A limit set inside an
unmeasured interval cannot be judged correct or incorrect from existing data.

**R/t1 keeps `passed=false` under v1.0.0 and under v1.1.0.** The Lead's reasoning for
not re-grading, recorded verbatim as the governing rule:

> It would convert the round's only terminal_passed=true into the headline success on
> the strength of a threshold change I made after seeing it fail. The mission forbids
> adjusting the acceptance rule to manufacture success; that does not stop applying
> because the argument happens to be good. Correct order is calibrate-then-regrade,
> not regrade-then-justify.

The gripper finding is recorded as an **open calibration defect**, not a resolved one.

### 4.5 Required follow-up (specified, NOT run — sim lane owns the lock)

```
G1  genuine grasp of the 35 mm block (close until stalled/reached_goal); full span
G2  T08 push (have it: R/t1, 3.06 mm)
G3  closed-finger sweep, no object (servo/contact noise floor)
```

Decision rule, fixed **before** the runs:

- `G1` and `G2` separated by more than `max(G3, 3*G3)` => a data-justified threshold
  exists at their midpoint.
- Overlap within the G3 noise band => travel **cannot** discriminate on this robot and
  the gate needs a different observable, not a different number.

2 runs, no model calls.

## 4b. F13 — the limits divergence is a LIVE FALSE-REJECTION path

Not merely a test-coverage gap. Confirmed on the real batch:

```
evaluate.py:223  max_lift = float(want.get('max_lift_during_m', 0.005))
   the T08 spec does NOT declare max_lift_during_m, so the TERMINAL clause
   silently falls back to the hardcoded 0.005.
evaluate.py:327  'max_lift_during_m': float(_push.get('max_vertical_m', 0.020))
   the EVIDENCE layer is handed the spec's max_vertical_m = 0.020.
```

R/t3, measured on one run:

| layer | max_lift_m | allowed | verdict |
| --- | --- | --- | --- |
| terminal clause | 0.0072 | 0.005 | **reject** |
| evidence `no_lift` | 0.007201 | 0.020 | accept |

The terminal layer is **stricter than the spec it is grading** — a false-rejection
direction defect. v1.1.0's `no_lift` uses the spec-derived limit consistently; the
terminal clause needs a separate decision because 0.005 is a frozen default in
`evaluate.py`, and changing it changes what success means.

## 4c. Benchmark-level caveat for any re-grade

Per the Lead's vacuity scan (`evobot_lead_benchmark_vacuity_20261112/`): 16 of 72
training instances have a placement clause satisfied at t=0 (4 fully vacuous). Any
v1.1.0 re-grade table **must report, per instance, how many clauses were free**, or it
will silently compare instances of different difficulty.

## 5. Applying

```
git apply patches/01-verify-v1.1.0-bind-rest.patch   # etc, in order
python3 -m pytest benchmark/evidence/ -q             # 81 existing + audit tests
python3 setup/acceptance/evobot_t08_gate_audit_20261112/reproducers/repro_9gate_audit.py
```

The 14 `xfail(strict=True)` tests in `benchmark/evidence/test_gate_audit_20261112.py`
will flip to **XPASS** as each patch lands, and `strict=True` turns XPASS into a
failure. That is the intended workflow: promote each test to a plain `assert` when
its defect is fixed.

## 4d. I made the same mistake I was auditing (recorded)

My first proposed `evaluate_v0.6.0.diff` also "fixed" F13 by changing:

```python
max_lift = float(want.get("max_lift_during_m", 0.005))
# -> want.get("max_lift_during_m", want.get("max_vertical_m", 0.005))
```

**That was wrong, and I caught it by running the patch against the batch.** It flipped
R/t3 from `passed=false` to `passed=true` — the exact failure mode this audit exists to
find, committed in my own fix.

Why it was wrong: the two fields bound **different quantities**.

| field | what it bounds | how it is computed |
| --- | --- | --- |
| `max_vertical_m` (0.020) | **end-state** height difference | `dz = abs(end[2] - start[2])` |
| `max_lift_during_m` (0.005) | **peak** height over the whole trace | `lift = max_z - start[2]` |

Measured on R/t3: `dz = 0.0` but `lift = 0.007201`. A push can ride up mid-motion and
settle at rest — substituting one bound for the other silently relaxes the no-lift rule.

Whether a 7.2 mm mid-motion lift violates T08 is a **task-design question the spec never
answered** (it declares `max_vertical_m` but no `max_lift_during_m`). Neither layer may
invent the answer. `evaluate.py:327` already commits this category error when it passes
`max_vertical_m` **as** `max_lift_during_m` to the evidence layer — my patch would have
propagated it, not fixed it.

**Corrected patch:** the F13 change is removed entirely. `evaluate_v0.6.0.diff` now
contains **only** the F14 overshoot/undershoot reason. Re-verified: **0 verdict flips**
across all 10 trials, F14 still fixed.

F13 remains an **open defect** requiring a task-design decision, not a version bump:
either the T08 spec should declare `max_lift_during_m` explicitly, or the hardcoded
0.005 default should be documented as intentional. Recording it as an open question is
the correct outcome; silently picking a number is not.

## 4e. Why the gripper limit STAYS at 0.002 this round

Disposition of F18, with the Lead's bimodality observation adopted and a numeric
correction to my own count.

### The distribution (n=9 with gripper telemetry)

`R/t4` is **excluded**: its evidence bundle is invalid (the recorder zero-interval
defect), so no gate ever evaluated its aperture and there is **no measured travel** for
it. My earlier "3 of 10" was wrong — it counted a trial whose gripper evidence does not
exist. Correct count: **2 of 9**.

| trial | travel | gate | terminal |
| --- | --- | --- | --- |
| **S/t3** | **0.0130 mm** | ok | **PASS** |
| S/t5 | 0.0270 | ok | — |
| R/t2 | 0.132 | ok | — |
| S/t2 | 0.234 | ok | — |
| S/t1 | 0.970 | ok | — |
| R/t5 | 1.037 | ok | — |
| R/t3 | 1.287 | ok | — |
| **R/t1** | **3.0570 mm** | **FAIL** | pass |
| **S/t4** | **4.8240 mm** | **FAIL** | pass |

**2 of 9 (22%) exceed the bound, and both are terminal-passing trials that the gripper
gate alone killed.** The one genuine pass sits **154x below** the limit and **235x below**
the smallest exceeding trial.

### The distribution is bimodal with a real gap — and that is why the number stays

The nine travels fall into two clusters: **seven between 0.013 and 1.287 mm**, then
**3.057 and 4.824 mm**, with **no trial between 1.287 and 3.057 mm**.

A threshold anywhere in that gap would separate these nine samples. But there are
**zero measurements inside the gap**, so any cut point there is a **post-hoc choice**.
The data therefore proves two things at once:

1. the 2 mm bound is **too tight** (22% false rejection on ordinary non-grasping pushes);
2. the data **cannot tell us what the right value is**, because the separating interval
   is unobserved.

**The limit stays at 0.002 this round — not because 2 mm is defensible, but because the
alternative is a number picked after seeing the failures.** That is the same rule that
kept R/t1 at `passed=false`. If it applies to a threshold that would help a trial pass,
it applies equally to one that would help a gate pass.

### What would settle it

The G1/G2/G3 experiment in `FINDING_F18_GRIPPER_CORRECTION.md` §4, with the decision
rule fixed **before** the runs. Until it exists, F18 is an **open calibration defect**
with a measured false-rejection rate of 22% (n=9), not a resolved one.

## 4f. S/t3 — the round's one pass, and how heavily it was verified

Stated plainly because it is the strongest single result the round produced:

> **S/t3 is the most heavily verified single trial this project has produced.**

It holds under **four independent combinations**:

| evaluator | verifier | verdict |
| --- | --- | --- |
| evaluate.py v0.5.0 (frozen, as graded) | verify.py v1.0.0 (as graded) | **pass** |
| evaluate.py v0.6.0 (corrected patch) | verify.py v1.0.0 | **pass** |
| evaluate.py v0.5.0 | verify.py v1.1.0 (strictly stricter) | **pass** |
| evaluate.py v0.6.0 (corrected patch) | verify.py v1.1.0 | **pass** |

It also survived my hostile re-derivation from the raw artifacts: honest `rest_height`
(0.0175, bound to spec), honest `max_z` (recomputed from 3310 physics rows), gripper
`n=1596` travel 0.013 mm, both real gripper links with 7 overlapping contact intervals,
teleport declared == measured to 1e-6, zero dropped samples, window contains every
sample, final position 18.4 mm inside a 60 mm zone, protected-object excursion
0.000000 m, displacement 117.32 mm with cosine 0.99833.

**It is a genuine push, it came from the single-shot CONTROL arm, and it must not be
cited as evidence that the closed-loop recovery works** (R scored 0/5).

## 4g. A defect I found in my own patch, and why it is recorded here

This is the single most important entry in this document.

My first `evaluate_v0.6.0.diff` also "fixed" F13 by substituting `max_vertical_m` for
`max_lift_during_m`. When I ran it against the batch it **flipped R/t3 from
`passed=false` to `passed=true`** — the exact failure mode this audit exists to catch,
committed inside the fix.

I caught it by executing the patch rather than reading it, removed the change, and
re-verified: **0 verdict flips across 10 trials**, F14 still fixed, and the corrected
patch still closes F1/F2 (below) and F7.

**Why this is recorded prominently rather than quietly corrected:** the round's own
headline was at stake. A verifier "upgrade" that happened to convert a failing recovery
trial into a passing one would have been the most consequential false success available,
and it would have arrived wearing the authority of an audit. The property a verifier
upgrade must have is the one the corrected patch has: **it tightens without re-grading
history.**

## 4h. Property the corrected patch set holds

| property | value |
| --- | --- |
| verdicts changed across the 10 existing trials | **0** |
| F1 carry-as-push bypass closed | **yes** (v1.0.0 accepts, v1.1.0 rejects) |
| F7 unsealed manifest closed | **yes** |
| honest push still accepted | **yes** |
| frozen files modified | **none** (`git diff` on evaluate.py, verify.py, schema.py, recorder.py, fixtures.py, benchmark/tasks, push.py, sim_profile.py is empty) |
