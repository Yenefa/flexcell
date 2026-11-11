# The A-prime execution batch cannot run: there is no `run_composite` action server

**Date** 2026-11-12 · **Found by** the Lead while the batch stalled · **Status: CONFIRMED, offline + one aborted launch**
**Effect: P0's A-prime execution is blocked by missing infrastructure, not by anything about A-prime.**

---

## 1. What happened

The A-prime execution batch (`evobot_p0_aprime_execution_20261112/run_aprime_batch.sh`) launched the
simulator, then waited up to 90 s per task for a `run_composite` action. It never appeared. The batch
script exited; Gazebo was left orphaned (cleaned up).

## 2. The cause

`benchmark/tools/run_composite_plan.py:87` creates an action client for **`run_composite`**:

```python
client = ActionClient(node, run_composite, "run_composite")
if not client.wait_for_server(timeout_sec=30.0):
    return {"error": "run_composite action server unavailable"}
```

**No such server is built or launched.** Two independent checks:

| Check | Result |
| --- | --- |
| Executables installed by `flexcell_skills` | `carry_server`, `move_to_pose_server`, `observe_server`, `pick_server`, `place_server`, `task_fsm_server`, `verify_server` — **no `composite_server`** |
| `trusted_sim.launch.py` mentions `composite` | **0 times** |
| Actions actually advertised by a live stack | `/move_to_pose`, `/pick_object`, `/place_object`, `/observe`, `/move_action`, `/gripper_controller/gripper_cmd`, `/execute_trajectory` — **no `/run_composite`** |

The `RunComposite` **interface** exists (`flexcell_interfaces/action/_run_composite.py`), so the action
type is defined. What is missing is the **server node**.

## 3. Why this was not caught earlier

I built the batch on the assumption that the 16 archived T14 runs had used
`run_composite_plan.py` — because that is the tool in the repo, and the archived plans are in its
input format. **I did not verify that the tool can run at all.**

This is the **fourth** premise-level error I have made this round, and it is the same shape as the
other three: inferring from an artifact's name or format rather than testing the thing itself. The
corrective I adopted after the third one — *read one record before building on an archive* — would
not have caught this one. The stronger corrective is: **before building a batch, run the smallest
possible instance of the pipeline end to end.** A single `ros2 action list | grep run_composite`
would have cost one command and saved the launch.

## 4. What this does and does not invalidate

| Claim | Status |
| --- | --- |
| A-prime's executor plan is identical to B's on 16/16 | **UNAFFECTED** — measured from plan files, no execution involved |
| A-prime is 36/36 correct on T12/T13/T14 | **UNAFFECTED** — planner-only |
| The 16 archived T14 runs are arm B, not A-prime | **UNAFFECTED** — read from `agent_reply.json` |
| B's four numbers (16/16, 11/16, 14/16, 16/16) | **UNAFFECTED** — graded from archived artifacts |
| A-prime execution and evaluation | **BLOCKED_INFRA** — no composite server exists |

So the plan-level P0 result stands. What cannot be measured is whether A-prime's identical plan
**survives execution** — and that is the one remaining question P0 needs answered.

## 5. What it would take

Either:

1. **Build the missing `composite_server`** — the interface exists, the executor logic presumably
   exists in whatever produced the archived T14 runs. This is real work and needs a decision about
   whether to reconstruct it or to find the build that had it.
2. **Re-express A-prime's plan in the form the EXISTING servers accept** — drive
   `pick_object` / `place_object` / `move_to_pose` directly instead of `run_composite`. This changes
   the executor path, which breaks fairness condition 3 of the P0 comparison, so it would need to be
   applied to **both** arms to stay fair.

**Option 1 preserves the comparison; option 2 changes it and must be applied symmetrically.** Neither
is something I should choose unilaterally, because option 1 may mean reconstructing a component whose
original build is unknown.

## 6. How this was found

Not by reading code. By noticing that the batch produced no `execution.tsv`, checking whether the
process was alive, finding Gazebo running with no batch, and then asking the live stack which actions
it advertised. The absence of `/run_composite` in that list is the whole finding.

**A stalled batch that leaves an orphan is a signal, not a nuisance.** Had I only killed the orphan
and retried, this would have looped indefinitely.
