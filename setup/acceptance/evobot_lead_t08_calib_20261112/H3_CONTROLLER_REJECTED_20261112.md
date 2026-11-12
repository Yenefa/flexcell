# H3 is real too: `execution_send_status: rejected` - the controller refused the approach

The objective lists separating H1 (contact geometry not re-established) from H3 (the controller
not executing the commanded trajectory) as critical-path item 2. Rounds 61-74 answered H1. This
round finds H3, in the same runs, as a distinct and separately-coded failure.

## The two records

| run | request | outcome | error_code | **execution_send_status** | ik_precheck |
| --- | --- | --- | --- | --- | --- |
| successful | `stage` | FAILED | 31 | **unavailable** | ok, solution found |
| successful | `target_box_a` | SUCCEEDED | 0 | None | ok |
| failed | `stage` | FAILED | 31 | **unavailable** | ok, solution found |
| failed | `target_box_a` | FAILED | **20** | **rejected** | ok, solution found |

## What this says

**`execution_send_status: rejected` means the trajectory was planned and then the execution
request was refused downstream.** IK found a solution (`ik_precheck.ok: true`) in every case,
including the failing one, so this is not a reachability problem.

That is H3 exactly: the controller did not execute what it was sent.

## And the staging move always reports FAILED

`stage` carries `error_code 31` with `execution_send_status: unavailable` in **both** the
successful and the failing run. So the staging move fails the same way whether or not the run
succeeds - it is a constant, not a discriminator.

`unavailable` differs from `rejected`: the send path was not available at all, rather than
refusing. The staging goal is issued with `motion_profile: ""` while the approach uses
`demo_slow`, which is the most obvious difference to chase.

**The pitch still changed in runs where staging reported FAILED** because the arm moves before
the send path fails - which is why the staging effect measured in earlier rounds is real despite
a failed outcome every time.

## Why this matters for the three modes

| mode | what it is now known to be |
| --- | --- |
| A drag-back | geometry: the horizontal retreat sweeping the fingers back through the box |
| B no-push | contact made, box barely moves - still **UNKNOWN** |
| C no-op | the approach was **rejected by the controller**, so the arm never moved |

**C is H3. A is H1.** B remains unattributed.

## What is not answered

- **Why the controller rejects.** `error_code 20` is not in the `error_codes.py` enumeration,
  which lists 0,1,2,10,21,22,23,24,25,26,30,32,33,34,35,41,52. A code of 20 appears there
  nowhere, so its meaning is **UNKNOWN** and I am not going to guess it.
- **Whether the rejection is transient or state-dependent.** One instance.
- Whether `motion_profile: ""` on the staging goal is what makes the send path unavailable.