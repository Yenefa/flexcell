# Independent verification of the T08 'Generalization Tested at n=2' claim

**Reviewer** gate-auditor · **Date** 2026-11-12 · **Constraints** read-only, no sim, no model calls,
no pinned file or `evolution/` touched.

---

## 0. Verdict up front

| question | answer |
| --- | --- |
| Q1 are seed3000/3002 unseen? | **QUALIFIED YES** — genuinely never validly instantiated before this batch, but **seed3001 is burned** and the claim must not say 'never run' |
| Q2 nine gates + COMPLETE over a real trajectory? | **CONFIRMED** — I re-ran the verifier and reproduced both verdicts exactly |
| Q3 what is COMPLETE_EVIDENCE_CONTRADICTS_PUSH? | **SERIOUS, not benign — but it is firing on a gate I previously found miscalibrated, and the physics contradicts its verdict** |
| Q4 is n=2 'Generalization Tested'? | **NO.** I would write **'Simulation Tested — 2 clean held-out instances, n=2'** |

**The claim survives as a statement about gate-passing runs. It does not survive as a statement about
capability, and it understates what the robot actually did.**

---

## 1. Q1 — the split: your directory-name inference happens to be right, for a reason worth recording

You inferred 'U means unseen' from a name. I checked the definition instead, and the name is
correct — but not because it is a name.

`benchmark/generate_t08.py` is the authority:

```python
# DEV vs HELD APART FROM THE START
#   Instances 2000-2002 are the development set: they may be used to tune the skill.
#   Instances 3000-3002 are written now but must NOT be run until the skill implementation is frozen.
HELD = [(3000, ...), (3001, ...), (3002, ...)]      # line 89
write(HELD, 't08_unseen', WT/'benchmark'/'tasks'/'t08_unseen')   # line 107
```

So: `HELD`, written into `t08_unseen/`, each spec carrying `split: t08_unseen`.
**The split is real and pre-dates the skill.** That part of the claim holds.

### But they were run before, and one of them was used to build the fix

`setup/acceptance/evobot_t08_evidence_loop_20261112/results.tsv` lines 12–17:

```
T08-push-seed3000  U       3000  ...  INCOMPLETE_OR_INVALID_EVIDENCE
T08-push-seed3001  U       3001  ...  INCOMPLETE_OR_INVALID_EVIDENCE
T08-push-seed3002  U       3002  ...  INCOMPLETE_OR_INVALID_EVIDENCE
T08-push-seed3000  U_shot  3000  ...  INCOMPLETE_OR_INVALID_EVIDENCE
T08-push-seed3001  U_shot  3001  ...  INCOMPLETE_OR_INVALID_EVIDENCE
T08-push-seed3002  U_shot  3002  ...  INCOMPLETE_OR_INVALID_EVIDENCE
```

All six ran in round 1 with the wrong world geometry. **That is the defensible reading of
unseen: those runs never instantiated the declared poses, so they measured nothing about those
instances** — you cannot have 'seen' an instance you never actually put on the table. Under that
reading this batch is the **first valid instantiation**, which is what the README means by
*'t08_unseen becomes a genuinely frozen unseen set for the first time'*.

Two caveats you must carry into the wording:

1. **seed3001 is burned.** The pose fix's own integration test targeted it explicitly —
   README section 4: *'integration on seed3001 (worst case, 70.7 mm)'*. It was used to validate the
   instrumentation. It is the one that failed here. **Do not count seed3001 as unseen.**
   Your n=2 correctly excludes it, but only because it failed, not because you excluded it a priori.
2. **'Never run' would be false.** Write *'first valid instantiation'*, not *'never executed'*.
   The distinction is the same one I enforced on the T14 archive: an invalid run is not a
   measurement, but it is still a run.

**Calibration used dev, not unseen — I checked.** `calib_G1` and `calib_G3` both run
`t08_dev/T08-push-seed2000.json`. So the gripper bound was not tuned on the unseen set. That is a
real point in the claim's favour.

---

## 2. Q2 — the nine gates: CONFIRMED by independent re-execution, not by reading a flag

You asked whether `evidence_status: COMPLETE` is consistent with the bundle or just self-reported.
It is **computed**, not reported: `verify.py:474-477` derives it from the gate list. So the check
is whether the gates really pass on the archived bundle. I re-ran it rather than trusting the log:

```
U_shot/seed3000  archived=COMPLETE  mine=COMPLETE  MATCH=True   9/9 gates ok
U_shot/seed3002  archived=COMPLETE  mine=COMPLETE  MATCH=True   9/9 gates ok
U_shot/seed3001  archived=COMPLETE_EVIDENCE_CONTRADICTS_PUSH  mine=...  MATCH=True
U/seed3000       archived=COMPLETE_EVIDENCE_CONTRADICTS_PUSH  mine=...  MATCH=True
U/seed3001       archived=INCOMPLETE_OR_INVALID_EVIDENCE      mine=...  MATCH=True
U/seed3002       archived=INCOMPLETE_OR_INVALID_EVIDENCE      mine=...  MATCH=True
```

Six of six reproduce. The two passes are real, over real trajectories
(**6680** and **6500** samples), with the nine gates: terminal, trajectory, table_support,
protected_unmoved, no_lift, pusher_contact, gripper, no_attachment, no_teleport — all ok true.

Numbers behind them: seed3000 displacement **147.14 mm** (band 30–150), cosine **0.9963**, vertical
**0**, in-zone **48.3 mm** of 60, max_lift **0.788 mm**; seed3002 **140.99 mm**, cosine **0.9950**,
vertical **0.02 mm**, in-zone **42.7 mm**, max_lift **0.02 mm**. Protected object excursion 0.0 on
both. `no_attachment` events 0 on both.

### My own error, recorded because it is the one you would not see otherwise

My first re-run said both runs **failed** `no_lift` and `gripper`, contradicting the archive.
That was **my mistake**: I called `verify(bundle, terminal)` without `limits`, and those two gates
correctly **fail closed** with *'no lift limit supplied'* / *'no calibrated aperture-change bound'*.
Re-run with the pipeline's own limits (0.02 / 0.002 / 0.005), everything matches.
The fail-closed behaviour is right; my invocation was under-specified. I mention it because a
reviewer who reports a discrepancy without chasing it is not reviewing.

---

## 3. Q3 — what COMPLETE_EVIDENCE_CONTRADICTS_PUSH means, and why it matters here

From `verify.py:478-483`:

```python
elif gates[1]['ok'] and all(g['gate'] not in ('trajectory','terminal') for g in failed):
    physical_outcome = PHYSICAL_NOT_PUSHED
    evidence_status = 'COMPLETE_EVIDENCE_CONTRADICTS_PUSH'
```

**It is not benign.** It means: *the bundle was readable and schema-valid, and at least one physical
gate says the push did not happen.* It is a positive claim of failure, not an absence of evidence
— that is `INCOMPLETE_OR_INVALID_EVIDENCE`, the third branch. **Your exclusion is correct.**

### But the gate that fires here is the one I flagged in the gate audit

Both exclusions fire on **`gripper`**, not on any geometric clause:

| run | push clause | displacement | cosine | vertical | in zone | gripper |
| --- | --- | --- | --- | --- | --- | --- |
| U_shot/seed3001 | **ok true** | 144.0 mm | 0.9906 | 0.00000 | yes | 0.0035 vs 0.0020 **FAIL** |
| U/seed3000 | **ok true** | 121.7 mm | 0.9976 | 0.00000 | yes (23 mm) | 0.0030 vs 0.0020 **FAIL** |
| U/seed3002 | **ok true** | 46.5 mm | 0.9893 | 0.00000 | yes | bundle schema invalid |
| U/seed3001 | ok false | 150.5 mm | 0.9894 | — | — | overshot the 150 mm ceiling (genuine) |

**And the run's own record says so.** `U/seed3000/t1/trial_record.json`, `failure_detail`:

> *'the gripper aperture moved more than the calibrated bound during the window; on this arm the
> fingers are deflected by contact, so the bound is being crossed by a push'*

### The physics contradicts the 'grasp' interpretation

The gripper gate exists to catch *grasp-and-carry*. A carry lifts the box. **These did not:**
vertical displacement **0.00000**, max lift **0.39 mm** (limit 20 mm), `no_attachment` events **0**,
and the box travelled 144 mm **along the table** into the zone. A box that is never lifted and never
attached is not being carried. The aperture change is finger deflection during contact — exactly
what the record says, and exactly the failure mode I reported in the gate audit (F8: the gripper
bound sits 154x below the pass value and 235x below the smallest genuine exceedance; the distribution
is bimodal with no samples between 1.287 and 3.057).

### So: benign or a finding in its own right? **Both, and you must say both.**

- As a **pass criterion**, your exclusion is right and must stay. A run that fails a gate is not a
  clean pass, and you should not re-admit it by argument after the fact.
- As a **statement about the robot**, the label `COMPLETE_EVIDENCE_CONTRADICTS_PUSH` is false here.
  The evidence does not contradict a push; it contradicts a *grasp*, and the gate cannot tell the
  two apart when the fingers are compliant and in contact.

**Consequence for the number:** n=2 is a correct count of runs that pass every gate, and an
**undercount of physical capability** — at least two more runs pushed correctly and were rejected by
a miscalibrated gate. If you report 2, say *'2 clean; 2 more pushed correctly but fail the gripper
bound, which is under calibration review'*. If you report 4, you must first fix or re-calibrate the
gate — not re-label the runs.

---

## 4. Q4 — is n=2 'Generalization Tested'? No. Here is the word I would use.

**I would not write 'Generalization Tested'.** I would write:

> **Simulation Tested — T08 push, 2 clean held-out instances (n=2), zero false success.**

Reasons, in order of weight:

1. **The denominator is chosen after the results.** Six runs exist over the three instances, on two
   arms (U and U_shot). Both arms were run on all three seeds. The claim keeps the arm that passed
   and drops the arm that failed. That is arm selection unless U_shot was declared the primary arm
   **before** the batch. **I could find no pre-registration naming U_shot primary**
   (`run_batch_v2.sh` takes the arm as a parameter and defines no primary; no preregistration file
   names it). Until that exists, the honest denominator is 6 runs on 3 instances, of which 2 passed.
2. **n=2 from one template family is not a generalisation measurement.** Both clean passes are T08
   push on geometries 30 mm apart in a family whose tolerance band is 30–150 mm. Two points cannot
   distinguish 'the capability works' from 'these two geometries work'.
3. **The capability is demonstrably stochastic on the same instance.** `U/seed3000` and
   `U_shot/seed3000` are the **same task** (`task_sha256` identical, `ede25524…`), same
   `contact_height_m` 0.02, same attempts=1, 2 minutes apart — and they gave 121.7 mm vs 147.1 mm
   with opposite verdicts. With within-instance variance that large, a 2/2 is not distinguishable
   from a coin landing heads twice.

What **would** license 'Generalization Tested': a pre-registered arm, a pre-registered n (at least
5 per family is the weakest defensible), the full denominator reported including failures, and the
gripper gate either calibrated or explicitly recorded as an open constraint on the claim.

---

## 5. What I would actually put in the record

```
T08 push — Simulation Tested, held-out instances first validly instantiated 2026-11-12.
  2 clean passes / 3 instances validly attempted / 6 runs across 2 arms.
  All 9 evidence gates verified by independent re-execution of verify.py v1.0.0
  on the archived bundles (6/6 verdicts reproduced).
  Zero false success. Zero lifts, zero attachments, protected object untouched in all runs.
  NOT claimed: generalization. n=2 is below any honest threshold, the arm was not
  pre-registered, and within-instance variance is large enough that 2/2 is not separable
  from chance.
  OPEN DEFECT: the gripper bound (0.002 m) rejects at least 2 runs whose physics shows a
  correct in-zone push with zero lift and zero attachment. Under calibration review.
```

Two wording corrections to carry:

| item | correction |
| --- | --- |
| Arm selection | report both arms, not the passing one |
| seed3001 | burned by the pose-fix integration test; never count as unseen |

---

## 6. The four numbers you have published, and this one

You published 9, then 5, then 3, then 2. This review says **2 is the first of those that is
defensible as a count** — because I re-ran the verifier and it reproduces — **and that it is still
not 'Generalization Tested'.** The narrowing was not the error. The error was the label on top of
the number.

The single change that would make this claim strong is not a bigger n. It is **fixing or honestly
scoping the gripper bound**, because right now the gate that decides 'push vs grasp' cannot tell
them apart on this robot — and that affects every T08 number this project has published, including
the ones that went the other way.
