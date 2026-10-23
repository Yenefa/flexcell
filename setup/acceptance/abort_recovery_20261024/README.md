# Abort diagnostics and PICK recovery cleanup

PICK failure cleanup now removes the attached collision body and its world
object in one acknowledged planning-scene diff. A rejected cleanup or failed
gripper-open response returns `ERR_INTERNAL`, retaining the original motion
failure in detail, rather than advertising a recoverable motion failure.
Cancellation still preserves carry and attachment. Carry-stop is a request;
this change does not claim a confirmed physical release or table pose.

Task abort diagnostics now retain the actual latest skill reply separately
from policy history. In particular, OBSERVE errors 2 and 3 remain
`ERR_INTERNAL` and `ERR_WORLD_STATE_UNAVAILABLE`; a missing reply remains
`ERR_TIMEOUT`. Frozen history inputs, action choices, recovery budgets and
task-level 50/51 classification are unchanged.

## Validation

See `receipt.json` for the tested source revision and hashes.

- Fresh ROS Jazzy build: interfaces, skills and native Gazebo plugin succeeded.
- Fresh-install `colcon test`: **262 tests, 0 errors, 0 failures, 0 skipped**.
  Seven new tests cover real OBSERVE errors, transport timeout, successful
  intervening OBSERVE, LIFT cleanup, rejected cleanup, gripper failure and cancel.
- Static attribute scan: 36 files, 0 problems; `git diff --check` passed.
- The actual Python cleanup message (`cleanup.cdr`) was consumed by MoveIt
  Core 2.12.4 in process. Both attachment and world body were cleared; adding
  the object for the next PICK no longer caused a start-state collision.
  `moveit_scene_result.log` is the result; this is not a Gazebo acceptance run.

To repeat the MoveIt check with ROS Jazzy and MoveIt Core sourced:

```bash
cmake -S setup/acceptance/abort_recovery_20261024 -B /tmp/pr40-scene-build
cmake --build /tmp/pr40-scene-build
/tmp/pr40-scene-build/scene_repro \
  setup/acceptance/abort_recovery_20261024/cleanup.cdr
```

## GPU regression and historical episodes

The fixed five-episode plan remains `S4:2 S5:2 S1:1`, policy `jev`, stage
`smoke`. The home GPU host `100.87.190.44` is online in the local Tailscale
status, but SSH authentication for `fuker` rejected the current public key.
**The GPU regression is NOT_RUN. No home inference process was started.**
Before starting inference, establish working remote process control and record
the server PID, executable and creation time. Verify the existing Clef weights
and profile, cold-start rebuilt source with a new runtime fingerprint, and run
the five episodes once. Shut down that specific inference process in cleanup,
including on test failure; verify exit and retain the shutdown receipt.

`historical_episode_inventory_local.json` maps all 176 original references.
Their exact filenames are missing on this laptop. The original desktop is
offline in Tailscale, and the home host has not been searched because SSH is
unavailable. This inventory is not a claim that the originals are lost.
Original records remain untouched; do not recreate or rerun these episodes.
