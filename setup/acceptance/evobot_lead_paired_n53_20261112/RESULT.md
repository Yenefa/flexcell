# RESULT: the run is VOID — 2 of 2 trials died at node creation, 0 usable observations

**Date** 2026-11-12 · **Status: FAILED RUN. No result is claimed.**
**The pre-registration in this directory stands unchanged and was not revised to fit anything.**

---

## 1. What was attempted

The paired n≈66 recovery experiment registered in `PREREGISTRATION.md` at 07:32, before any outcome existed.
`run_paired.sh` called the existing evidence script **unmodified**, once per 11-trial chunk, rotating
`ROS_DOMAIN_ID` per chunk (241–246) to avoid the measured CycloneDDS participant exhaustion from the T05 n6
batch.

## 2. What happened

```
=== chunk 1  ROS_DOMAIN_ID=241 ===
interface check: OK
=== trial 1 ===
  HARNESS_ERROR: push_object server never appeared
=== trial 2 ===
  HARNESS_ERROR: push_object server never appeared
=== trial 3 ===
```

**2 trials attempted, 2 void, 0 usable paired observations.** The run was killed after the second failure
rather than allowed to produce ~3 hours of `HARNESS_ERROR` rows.

## 3. Root cause — and why my domain fix did not help

`c1/t1/stack.log`:

```
rclpy._rclpy_pybind11.RCLError: error creating node: error not set, at ./src/rcl/node.c:252
[ERROR] [move_to_pose_server-6]: process has died [pid 718544, exit code 1]
[ERROR] [move_group-5]: process has died [pid 718543, exit code -6]
```

**The middleware cannot create a node.** `move_to_pose_server` and `move_group` both die before
`push_object` can appear, so the 90 s readiness wait expires every time. This is not a slow cold start and not
the domain-participant exhaustion I designed against — **the fix I spent the round on addressed a different
failure than the one that actually occurred.**

## 4. What was ruled out, and what was not

| checked | result |
| --- | --- |
| `/dev/shm` exhausted | **no** — 7.9 G free, 1% used |
| stale shared-memory segments | **6 entries**, not obviously leaked; **not proven innocent** |
| leftover simulation processes from earlier rounds | **1 `gz sim` still running after the run** — **not ruled out as the cause** |
| domain collision | **no** — chunk 1 used a fresh domain 241 |
| whether a clean restart would succeed | **NOT TESTED** — the round ended before it could be |

## 5. What this does and does not mean

| claim | status |
| --- | --- |
| the recovery pass-rate question is answered | **NO** |
| the pre-registered prediction was tested | **NO** — zero observations |
| the design is unworkable | **NO** — the harness failed before the design was exercised |
| the harness has a real fault worth fixing | **YES** — node creation fails under conditions not yet isolated |

**No threshold, evaluator, task or contract was touched. No result was inferred from a void run.**

## 5b. Isolation test (round 23) — the fault is DETERMINISTIC, not contention

Ran **one** trial with the environment cleaned first:

```
gz sim procs left: 0        shm entries: 2 -> 2 (cyclonedds/fastrtps segments removed)
single trial, fresh domain 251
  interface check: OK
  HARNESS_ERROR: push_object server never appeared
  'error creating node' occurrences in stack.log: 8
```

**It fails identically with nothing else running, a fresh domain, and cleared shared memory.** So the fault is
not residual contention from earlier rounds — **the simulation stack can no longer create ROS nodes in this
environment at all**, and it did so successfully in rounds 8–11.

**This is a hard blocker on any further Gazebo work, including the registered experiment, until the environment
is repaired.** No amount of re-running the batch will produce data.

## 6. What must happen before re-running

1. **Isolate the node-creation failure on a single trial**, with nothing else running, and confirm the stack
   reaches `push_object` before scheduling a batch. Scheduling 66 trials over a stack that has not been shown
   to start once is the mistake this round made.
2. **Clean up leftover `gz sim` processes** and clear `/dev/shm` segments before the next attempt.
3. **Re-run the pre-registration as written** — it is unchanged and still binding.

**The correct order was: prove the harness starts, then launch 66 trials. I inverted it.**