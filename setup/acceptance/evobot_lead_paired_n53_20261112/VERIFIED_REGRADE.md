# VERIFIED: the pilot's 4/5 reproduces exactly — and the `passed`/`terminal_passed` split is the real story

**Date** 2026-11-12 (round 37) · **Independent re-grade of stored artifacts with the frozen evaluator v0.5.0.**

---

## 1. What I did

Re-ran `benchmark/evaluators/evaluate.py` (frozen, pinned) over the pilot's **stored** `traj_t1..t5.json`, which
carry the `trajectory` key the clause requires. Nothing re-run in simulation; grading only.

```
trial  terminal_passed  passed   displacement  direction_cosine  inside_zone
  1        False         False      0.11036        -0.99975         False
  2        True          False      0.09071        +0.99988         True
  3        True          False      0.14446        +0.99997         True
  4        True          False      0.11430        +0.99986         True
  5        True          False      0.13231        +0.99898         True
```

**`terminal_passed`: 4/5 — the pilot's claim reproduces exactly, independently, from stored artifacts.**

Trial 1 is a genuine physical failure: the box went **backwards** (cosine −0.99975) and finished outside the
zone. That is the one the recovery loop could not rescue, and it is honestly a failure.

## 2. But `passed` is 0/5 — and that distinction is the whole finding

`evaluate.py`:

```python
253  terminal_passed = bool(clauses) and all(c["ok"] for c in clauses)
276  passed = terminal_passed
331  evidence = _verify_evidence(bundle, {"passed": terminal_passed}, _limits)
332  passed = bool(terminal_passed and evidence.get("passed"))
```

**`terminal_passed` is the geometric clause conjunction. `passed` additionally requires a verified evidence
bundle.** The pilot reported `terminal_passed`; the repository's stricter `passed` is **0/5** because no
evidence bundle was supplied to the gate verifier.

Both numbers are true and they answer different questions:

| number | what it means |
| --- | --- |
| **4/5 `terminal_passed`** | the robot reached the graded end state, with a valid push trajectory |
| **0/5 `passed`** | the nine-gate evidence verifier accepted no bundle |

## 3. So what is T08's status, honestly

| claim | level | evidence |
| --- | --- | --- |
| T08 terminal clause achieved **4/5** with ≤3-attempt recovery | **Simulation Tested, independently re-graded by me** | round-37 re-grade of stored artifacts |
| the same arm single-shot | **3/5** — trials 2,3,4 first attempts succeeded | pilot `recovery.tsv` attempts=1 |
| full `passed` (incl. evidence bundle) | **0/5** | no bundle supplied |
| **my own paired run, 0/26** | **VOID — withdrew round 36** | no trajectory in the state file |
| Generalization Tested | **NO** — one instance, seed2000, no unseen seeds | |

**The paired 3/5 → 4/5 result from round 20 stands** as the best available paired estimate, and it was right:
one discordant pair, and that pair is trial 5, whose first attempt failed and whose retry succeeded.

## 4. What is still missing for P2

The Master Goal requires T08 **fail-closed trajectory verification that cannot be faked by pick-carry-place**.
The trajectory requirement is met and working — that is why trial 1 correctly failed. **The nine-gate evidence
bundle is not being produced at all**, so `passed` is 0/5 while `terminal_passed` is 4/5.

**That gap is the remaining P2 work, and it is a harness/evidence-plumbing task, not a robot capability
problem.** The robot demonstrably reaches the graded end state four times in five with recovery.

## 5. The correction this forces on my own record

- **round 17's "the arm cannot do T08" — FALSE.** The arm reaches the end state 4/5. My ±3.44 mm figure
  measured pose repeatability, not task capability, and I attached a capability conclusion to it.
- **rounds 33/34/36's 0/26 — VOID.** Not a measurement of the robot.
- **round 20's paired 3/5 → 4/5 — CONFIRMED** by independent re-grade.

**The one thing I got right in the middle of this was the paired analysis, and the thing I got wrong was every
time I let a graded number stand in for the robot's behaviour.**