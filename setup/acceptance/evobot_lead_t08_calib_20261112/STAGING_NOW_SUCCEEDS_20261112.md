# The staging move now actually succeeds: 3 of 3, where it was 0 of every run before

The round-79 diagnosis was that the staging move races the controller action server. This round
waits for `/arm_controller/follow_joint_trajectory` before issuing it.

## Result

| repeat | controller ready? | **stage outcome** | ee descent |
| --- | --- | --- | --- |
| 1 | yes | **SUCCEEDED** | 0.0769 |
| 2 | yes | **SUCCEEDED** | 0.0804 |
| 3 | yes | **SUCCEEDED** | 0.0738 |

**Three for three.** Before the change, every staging move in every logged run returned `FAILED`
with `execution_send_status: unavailable` - the controller action server was not answering within
the 2 s timeout.

## The descent figure dropping is expected, not a regression

`ee_descent` is now 0.074-0.080 where it used to be 0.166. That is because the staging move
**actually arrives** at (0.35, y, 0.03), so the arm starts the approach much closer to the box and
has less to descend.

Previously the move failed partway, so the arm was still near its neutral pose (z 0.187) and the
whole descent happened inside the push phase. **The smaller number means the staging is working.**

It still clears the 10 mm `push_executed` threshold by 7x, so the guard from round 73 is unaffected.

## What this invalidates

**Every earlier measurement was taken with a staging move that never arrived.** Rounds 62-74
measured pitch changes and pass rates with the arm at whatever partial position the failed move
left it in - consistently around `link5_x_z -0.32`, which was real motion, but not the commanded
target.

So the earlier findings are not wrong - the pitch did change, the drag-backs were real - but they
describe a **different starting configuration** than the one the code asks for.

## What this does not tell us

- **Whether it improves the task success rate.** These three runs were not scored. Changing where
  the arm starts changes everything downstream, and the round-71 lesson stands: a change that
  looks right in three runs has already failed to replicate once.
- Whether the controller rejection (mode C) is affected. That is a separate status - `rejected`
  rather than `unavailable` - and waiting for the server does not address it.

## The next test

Full paired comparison with the wait in place: baseline vs retreat lift, seeds 2000 and 3001,
three repeats per cell, scoring zone membership and mode per run. **That is the same 12-run design
as round 70, so the two are directly comparable.**