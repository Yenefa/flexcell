# Lead: T08 full `passed: true` on what look like UNSEEN instances — unverified

**Date** 2026-11-12 (round 44) · **STATUS: LEAD, NOT A RESULT.** Resolves the open caveat in
`T08_FULL_PASS_EXISTS.md` that the count of 9 might be re-grades of the same trial.

---

## 1. The nine verdicts, enumerated

```
evobot_t08_contact_calibration_20261112/runs/H0200/t1/verdict.json
evobot_t08_evidence_loop_20261112/evidence/R/t1/verdict.json
evobot_t08_evidence_loop_20261112/evidence/S/t3/verdict.json
evobot_t08_evidence_loop_20261112/evidence/S/t4/verdict.json
evobot_t08_instance_pose_20261112/runs/U/seed3000/t1/verdict.json
evobot_t08_instance_pose_20261112/runs/U/seed3002/t1/verdict.json
evobot_t08_instance_pose_20261112/runs/U_shot/seed3000/t1/verdict.json
evobot_t08_instance_pose_20261112/runs/U_shot/seed3001/t1/verdict.json
evobot_t08_instance_pose_20261112/runs/U_shot/seed3002/t1/verdict.json
```

**They are nine distinct `(batch, run)` paths — not the same trial re-graded.** That was the open caveat, and it
is now resolved: the count is not an artefact of `verdict.json` and `verdict_after1.json` double-counting.

## 2. Why this may matter far more than the count

**Five of the nine are in `evobot_t08_instance_pose_20261112` under directories named `U/` and `U_shot/`, on seeds
`3000`, `3001`, `3002`.** In this repository's notation `U` means **unseen**, and seeds 3000–3002 are recorded in
my own fact table as **unseen seeds** (spent, but unseen relative to training).

**If those passes are legitimate, T08 has full-passed on three unseen instances — which is the territory of
Generalization Tested, the highest rung on the evidence ladder.** That would be the single strongest capability
result in this session and would materially change P2's status.

## 3. Why I am NOT claiming it

1. **`U` might not mean what I think.** I have not read the generator or the freeze manifest that defines these
   directories. Inferring the split from a directory name is exactly the kind of proxy substitution that cost
   this session twenty rounds.
2. **I have not verified the passes are legitimate** — i.e. that each supplied a valid `trajectory` and a
   passing nine-gate evidence bundle rather than being graded on a permissive path.
3. **n=3 instances, and two seeds appear in both `U` and `U_shot`** — seed3000 and seed3002 each yield two of the
   nine, so distinct instances number about three, not five.
4. **`U_shot` may be a different configuration entirely**, which would make those passes non-comparable.

## 4. What would settle it, in order

1. Read what defines the `U` / `U_shot` split — `benchmark/generators/unseen_tasks.py`, the freeze manifest, and
   the batch README for `evobot_t08_instance_pose_20261112`.
2. For each of the three seeds, confirm the verdict carries `trajectory_required` satisfied and that its
   `evidence` gates passed — not just the top-level flag.
3. Only then ask whether three unseen instances at full pass supports a Generalization claim, or is
   under-powered.

## 5. What this changes right now

**Nothing yet.** T08's status remains: terminal clause 4/5 Simulation Tested, full pass achievable, **Generalization
Tested: NOT ESTABLISHED**. What changes is that the ladder's top rung is **no longer obviously out of reach**, and
there is a specific, cheap path to check it that does not require the simulator.
---

## 6. Refinement after reading the batch (round 45)

### `U` and `U_shot` are probably closed-loop vs single-shot, not valid vs invalid

`U_shot` appears **nowhere** in `run_batch_v2.sh` or the batch README — so it is ad-hoc naming. `run_batch_v2.sh`
line 278 distinguishes *"the push itself: closed loop (or single shot)"*. **Most likely reading: `U` = unseen with
closed-loop recovery, `U_shot` = unseen with a single shot.** That is an inference from naming and **must be
confirmed against the run manifests**, not assumed.

### The invalidity concern does not apply to this batch

The README records that the **round-1** `t08_unseen` trials *"ran the dev world and were graded against unseen
geometry, with offsets up to 70.7 mm"*. `evobot_t08_instance_pose_20261112` is the batch that **fixes** that — it
carries `inject_instance_poses.py` and states that *"with poses actually instantiated, `t08_unseen` becomes a
genuinely frozen unseen set for the first time"*. **So runs in this batch have the geometry instantiated**, which
is what the earlier runs lacked.

### What that would mean, if confirmed

| pass | arm | significance |
| --- | --- | --- |
| `U/seed3000/t1`, `U/seed3002/t1` | closed-loop | unseen, recovery allowed |
| `U_shot/seed3000/t1`, `U_shot/seed3001/t1`, `U_shot/seed3002/t1` | **single shot** | unseen, **no retries** |

**Single-shot full passes on three unseen seeds would be stronger than the closed-loop ones**: they would mean
the task was completed on unseen geometry without the retry strategy, which is exactly what a Generalization
claim needs and what the pilot's 4/5 could not show.

### Still not claimed, and the reasons have narrowed to two

1. **Confirm the `U` / `U_shot` meaning** from the run manifests — naming is not evidence.
2. **Confirm each verdict satisfied `trajectory_required` and its nine-gate evidence bundle**, rather than
   inheriting a permissive path.

n is still **3 distinct instances**, and three is not a generalization study. But it is three unseen
instances at full pass, and that is a **categorically different claim** from everything else in this session.
