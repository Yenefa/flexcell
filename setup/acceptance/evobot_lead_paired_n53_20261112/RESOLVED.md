# RESOLVED: my 0/26 is a harness artifact — it never supplied the trajectory the clause requires

**Date** 2026-11-12 (round 36). This withdraws my own 0/26 as a T08 capability statement.

---

## 1. The mechanism, in three lines of `evaluate.py`

```python
221  # It FAILS CLOSED. If no trajectory is supplied the clause is False, never True:
227  traj = (final_state.get("trajectory") or {}).get(name)
253  terminal_passed = bool(clauses) and all(c["ok"] for c in clauses)
```

The trajectory must be a **`trajectory` key inside the state file** passed as `sys.argv[2]`.

**The state file my run wrote contains only:**

```json
{"objects": {"target_box_a": [0.0704, -0.0005, 0.01750, 0.0], ...}}
```

**No `trajectory` key.** So at line 227 `traj` is `None`, the clause takes the fail-closed branch at line 221,
`ok` is `False`, and `terminal_passed` is `False` — **for every trial, regardless of what the robot did.**

## 2. Therefore 0/26 measures nothing about the robot

| claim | status |
| --- | --- |
| "T08 scores 0/26 with recovery" | **WITHDRAWN. The harness never supplied the required evidence, so every trial was rejected by construction** |
| "recovery shows no benefit (0 discordant pairs)" | **WITHDRAWN — a test whose every observation is forced to the same value cannot detect an effect** |
| "the binding clause is push:target_box_a" | **TRUE but trivial** — it fails closed absent a trajectory, which is the design |
| "displacement is not the binding constraint" | **TRUE, and now fully explained** |
| trial 1 made a correct physical push (149.65 mm, cosine 0.99999, inside zone) | **STANDS** — that is what the robot did |

**The fail-closed design worked exactly as the Master Goal requires**: a push cannot be confirmed from terminal
geometry alone, so the clause refuses to pass without a trace. **I was grading a task with the evidence
deliberately withheld.**

## 3. Why the pilot's 4/5 is not refuted by this

The pilot's evidence directory contains `traj_t1.json` … `traj_t5.json` — **separate trajectory artifacts**. Its
state files evidently carried the `trajectory` key; mine did not. **So the pilot's run and mine are not
comparable, and my 0/26 cannot be used against its 4/5.**

The pilot's 4/5 therefore remains **the only T08 number produced with the evidence supplied** — and it still
needs independent re-grading, because `verdict_t1.json` shows `terminal_passed: False` with real geometric
failure (cosine −0.98753, outside zone). Its tsv records True for trials 2–5; that is consistent with each of
those trials having a valid trajectory, but **it has not been verified by me**.

## 4. What has to happen

1. **Merge `traj_t*.json` into the state file** before grading, exactly as the pilot did.
2. **Re-grade one pilot trial from stored artifacts** to confirm 4/5 is reproducible.
3. **Only then** re-run the paired experiment with trajectories supplied — the pre-registration still holds, but
   it was written against a harness that turned out to be starved of evidence.

## 5. The error, named

I spent rounds 17–35 treating the graded result as a measurement of the robot. **It was a measurement of my own
grading invocation.** The clause name `push:target_box_a` appeared in every verdict for twenty rounds, and the
`reason` string telling me exactly what was missing was printed in every one of them:

> *"no trajectory for this object: end state alone cannot prove it was pushed rather than carried"*

**I read that string as an explanation of a geometric failure instead of as an instruction about my harness.**
