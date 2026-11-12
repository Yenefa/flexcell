# Three failure modes, and one of them is a silent no-op

Round 71 grouped the four failing runs into two modes by their drag and push values. Looking at
the contact traces separates them properly - and finds a third that is not a geometry problem at
all.

## The four failing runs

| run | gripper-box contacts | box x | ee z over the push phase |
| --- | --- | --- | --- |
| seed 2000, lift 0.0, r1 | **1527** | 0.2200 -> **0.2486** (+x) | 0.0197 .. 0.1873 |
| seed 2000, lift 0.08, r2 | **946** | 0.2200 -> **0.2219** | 0.0212 .. 0.1874 |
| seed 3001, lift 0.0, r1 | **1840** | 0.2300 -> **0.2626** (+x) | 0.0214 .. 0.1875 |
| seed 3001, lift 0.08, r3 | **0** | 0.2300 -> **0.2300** | **0.1872 .. 0.1872** |

## Mode A - the drag-back

Runs 1 and 3. Heavy two-finger contact (1527 and 1840 contacts), the arm descends to the box,
the box moves, and it ends up **behind where it started** (+0.0286 and +0.0326). This is the
retreat carrying it back.

## Mode B - contact without displacement

Run 2. 946 contacts, the arm descends normally to ee z 0.0212, contact happens, and the box moves
**1.9 mm**. The gripper is at the box and the box does not go. Not a retreat problem - the push
fails at contact.

## Mode C - the arm never descends

Run 4. **Zero gripper-box contacts. ee z is 0.1872 for the entire push phase** - the exact
initial height, unchanged to four decimals. The arm never moved. The box is untouched.

This is the same signature as the round-53 staging failure and the round-60 seed-3002 zero-run:
**an action that returns without doing anything.**

## Why mode C matters most

Mode A and B are geometry and contact problems, which the work of rounds 61-69 addressed. Mode C
is a **silent no-op**: the push action reported a result, the timeline recorded a `push_1` phase,
and no motion occurred. Nothing detects it.

`stage_ok` was added for exactly this on the staging move in an earlier round. **There is no
equivalent guard on the push itself.**

## The rate, stated with its limits

12 runs, 8 successes, 4 failures: **2 mode A, 1 mode B, 1 mode C.**

With n=1 per mode, that split cannot be trusted as a distribution - it only establishes that all
three exist and can be told apart by contact count and ee height. Getting the split right needs
many more runs, and mode C needs a guard before the rate means anything, because a no-op counted
as a failure conflates 'the robot could not push it' with 'the robot did not try'.

## Not claimed

- The 2/1/1 split is not a distribution.
- Mode C's cause is unknown - whether it is the descent, the action dispatch, or the controller.
- T08 remains `CALIBRATION_UNSUPPORTED`.