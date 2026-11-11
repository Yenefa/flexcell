# P1's *recover* capability, measured for the first time: 18 of 24 (75%)

**Date** 2026-11-12 · **Zero Gazebo runs — measured from archived retry artifacts**
**This corrects my own hypothesis. I expected to find recovery unimplemented.**

---

## 1. What I went looking for, and what I nearly concluded

P1 requires *observe / plan / execute / **diagnose** / **recover***. I had no measurement of the last two. In the
archive I found:

- **110 runtime `recovery_decision.json` records, all `no_recovery`** — 104 *"first attempt succeeded"*, 6 *"goal
  already satisfied by measurement"*. So those runs never needed recovery.
- **26 richer records** where recovery actually fired: **24 chose `resume`**, 2 `no_recovery`.
- **0 of those 26 runs passed** — every one ended `outcome=1`.

That looked decisive: *recovery is declared and does not work.* **It was wrong**, and the way I caught it is
worth recording.

## 2. The error I made

I tested whether a retry had been executed by looking for a **sibling directory** (`-a2`, `attempt-2`). Found
none, and nearly wrote *"24 retry plans built, 0 executed"*.

Then I grepped for what **writes** `plan_retry.json` and what **reads** it. Nothing in `runtime/` reads it —
which supported the conclusion. But `setup/acceptance/evobot_unified_runner_20261111/run_batch.sh:113` does:

```bash
if [ -f "$D/plan_retry.json" ]; then
    python3 "$CLIENT" --plan "$D/plan_retry.json" --timeout 400 > "$D/task_retry.out" 2>&1
```

**The retry runs in the same directory and writes `task_retry.out`.** My directory heuristic was the bug, not
the code. **24 `task_retry.out` files exist.**

## 3. The measurement

| retry outcome | count |
| --- | --- |
| `outcome=0, error_code=0` — **recovered** | **18** |
| `outcome=1, error_code=62` — retry also failed | 4 |
| `outcome=1, error_code=60` — retry also failed | 2 |

**RETRY SUCCESS RATE: 18 / 24 = 75%.**

So of 24 episodes whose first attempt failed, **18 completed on the single permitted retry**. Recovery is
bounded to one attempt by design (`budget: 1`), and the 6 that failed were given no third chance — which is
the documented policy, not an accident.

## 4. Why this is honest rather than success-manufacturing

This is the part that decides whether 75% is a capability or a trick, so I checked the design rather than
taking the number:

| property | evidence |
| --- | --- |
| recovery is decided from **execution** evidence, never the graded verdict | `recovery_driver.py:2-7` states it and the code reads `task.out`'s `RESULT` line, never the evaluator |
| the evaluator is consulted **only after** all attempts, on the final world state | same docstring |
| the **original failure is preserved** | `original_failure_preserved: True` on all 26 rich records |
| there is a guard against retrying a *false* failure | `recovery_driver.py:57-63` — if the goal is already met by measurement, it records `no_recovery` instead of wasting a cycle *"and, worse, made 'arm R' look exercised when it was not"* |
| retries are **bounded** | `budget: 1` |

**Retrying a genuinely failed episode is recovery, not gaming**: the robot observed a failure, diagnosed it
from execution evidence, rebuilt or re-spread the plan, and tried once more. That is exactly what P1 asks for.

## 5. What this changes

| claim | before | now |
| --- | --- | --- |
| P1 diagnose | unmeasured | **fires correctly**: 26 failure classifications recorded (grasp / planning / UNKNOWN) |
| P1 recover | **unmeasured, and I suspected absent** | **18/24 = 75% on the single permitted retry** |
| episodes failing once then completing | unknown | **18** |

**This is the first measured robot-capability result in this project that is positive and independently
checkable from committed artifacts** — it did not need a new simulation run, and it was sitting in the archive
the whole time.

## 6. What it does not change, and I am not going to let it

- **It is not T08.** These are pick/carry/place episodes. **T08 skill-level remains 0/6** and its blocker
  (round 17: ±3.44 mm repeatability against a 2.5 mm cliff) is untouched.
- **It is not Generalization Tested.** The retries are on held-out instances that were used while the recovery
  behaviour was being developed; I am not claiming the 75% transfers to unseen seeds.
- **It does not raise the reported pass rates by itself.** Whether the baselines count the retry success or the
  original failure is a separate accounting question I have not audited, and **if they count the failure then
  the project has been understating its own capability** — that is the next thing to check, not a claim to make.

## 7. Reproduce

```bash
python3 setup/acceptance/evobot_lead_recovery_measured_20261112/analyse_recovery.py
```

Reads every `recovery_decision.json` and `task_retry.out`, reports the decision distribution and the retry
success rate. **No simulator, no model calls, no writes.**