# Grasp probe repair and next physical diagnosis — 2026-10-08

Source base: `c79e0c672c95e2d9cd04112ef42b65e4c67e1845`, the head of
[PR #28](https://github.com/Yenefa/flexcell/pull/28), which remains unmerged.
This follow-up belongs to #8 measurement integrity and the grasp-diagnosis
backlog described in E-021/#13. It changes a diagnostic client; the frozen carry
mechanism, skill servers, decision policies and recovery budget are unchanged.

## What is known

E-021 records cross-policy PICK failures followed by exhausted recovery. The
archived batch summaries contain task traces, but not the matching raw pick/
carry logs needed to distinguish attach geometry, motion execution, pose
sampling and carry service timing. The physical root cause remains **UNKNOWN**.
`archived_failures.json` inventories failures with each file hash and runtime
fingerprint; it does not pool or re-score historical results.

Before collecting further data, the old `111_grasp_probe.py` needed repair:

1. Missing goal/result replies allowed the loop to send another physical goal.
   No cancellation/terminal confirmation was required, and the CLI returned 0.
2. `--object target_box_b` still placed the object at A's hardcoded
   `[0.220, 0.000, 0.0175]`, changing the next trial's starting condition.
3. Success counted `error_code == 0`, even with default status, failed outcome
   or false `grasp_attached`. Default Pose fields also fabricated a rise when
   no after-pose had been measured.
4. Failed release was ignored, injection was not cleared, canonical trial
   independence was not checked, and reusing `--out` truncated existing data.

## Repaired diagnostic behavior

- Each physical goal is sent once. Acceptance/result uncertainty stops the
  probe. An accepted goal is cancelled with bounded waits; a cancellation
  acknowledgement alone does not prove termination. A late result is retained,
  but cannot turn that timeout into a passing trial.
- Reset never races an action whose acceptance or termination is unknown.
  Such a run records why cleanup was not attempted and exits nonzero; inspect
  the running stack before resuming. Confirmed terminal actions can be reset.
- Success requires matching ROS terminal status, typed skill outcome/status,
  zero error, grasp marker, finite measured poses and positive rise. An all-zero
  quaternion identifies an unpopulated/default Pose; no rise is invented from it.
- A successful pick is placed at its measured starting coordinates. Place
  must confirm typed success, release and a finite measured after-pose.
- Each trial starts after canonical reset and sealed injection clear. After a
  known terminal pick/place, cleanup reset must succeed before another trial.
  Both clean process exit and top-level boolean `ok: true` are required.
- True typed pick failures remain observations, including ERR_GRASP_FAILED.
  Harness errors remain separate and stop collection. All completed rows are
  flushed; existing output files cannot be overwritten. The default output is
  a unique file under `~/.ros/flexcell/grasp_probe/`.

Reset/homing and verified release change the experiment conditions relative to
the old consecutive-pick probe. Keep old and new runs separate. These are
diagnostic observations, not M3 cells or online benchmark qualification.

## Verification — E-024

Evidence: [`setup/acceptance/grasp_probe_20261008/`](../setup/acceptance/grasp_probe_20261008/).

- `reproduce_probe.py` runs both actual CLI revisions against synthetic ROS
  plumbing; no robot is contacted. `reproduction.json` retains the inputs and
  outcomes for default success, result timeout and B placement. The old CLI
  returns 0 and sends both picks in the first two cases; the repair returns 1
  and stops after one. B placement changes from A's coordinates to B's measured
  `[0.20, -0.18, 0.0175]`.
- **227 local ROS-independent tests passed**, zero errors/failures/skips,
  including **33 new regressions**. The tests exercise the actual diagnostic
  loop, CLI exit/cleanup, action timeout/cancellation boundaries, default-result
  rejection, measured poses, resets, injection clear and evidence preservation.
- Static scan: **35 source files, zero missing attributes**. Exact commands,
  source hashes and the eleven excluded ROS-dependent test files are recorded
  in `verification.json`.

ROS/Gazebo and live robot/model calls are **NOT_RUN** in this cloud environment.
ROS CI checks build/test compatibility separately. This repair does not prove
the physical failure fixed, complete model replay, qualify a new deployment,
or unfreeze n≥50.

## Next run on the simulation host

Review/merge the dependent PRs, rebuild the changed source and record the new
deployment identity. Start with a short independent diagnostic for each box:

```bash
python3 setup/111_grasp_probe.py --object target_box_a --trials 5
python3 setup/111_grasp_probe.py --object target_box_b --trials 5
```

Archive the resulting JSONL together with `pick.jsonl`, `place.jsonl`,
`carry.jsonl`, `move_to_pose.jsonl` and fleet/ROS logs for the same time window.
Use each pick/place `evidence_id` and action goal UUID to find the matching
server result. The full result detail and measured before/after positions
separate pre-lift attachment failures from post-lift sampling/follow failures.
Existing carry failure events and motion results can then test timing/service
hypotheses. Successful set-pose ticks and TF gaps still lack full telemetry in
the teleport profile; absence of a failure log is not proof of a working servo.
Any further carry instrumentation is a separate change under its freeze rule.
