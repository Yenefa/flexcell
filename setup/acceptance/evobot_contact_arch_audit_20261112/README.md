# Architecture/contact audit — base d87f1701

Review and priorities: `docs/ARCHITECTURE_REVIEW_20261112.md`.
**55 mm geometry configuration rejected; initial-world adapter verified.**
No new bounded-push capability, unseen task result, baseline promotion or L4 claim.

## Retained data, not a new success batch

`retained_contact_audit.json` audits all five primitive strokes of the previous
B1/B2/B3 batch and both executed strokes of pilot2. Old raw file hashes match the
published `evobot_push_feedback_20261112/raw_runs.zip` manifest. Those original
records stay in that archive; this archive does not duplicate or modify them.

Actual world EE poses are composed from native link5 plus its fixed 126 mm EE
transform. Five synthetic coordinate checks validate known rotations/inverses.
The contact classifications describe point locations in the object's local frame;
they do not measure the causal contribution of normal force or friction.

Key findings: B1's contact_made=false still has 140 native pusher-contact steps;
pilot2's reverse stroke has EE +62.6 mm versus object −16.9 mm; the five fixed-batch
strokes have per-step mean top-contact fractions about 0.64–1.00 and changing tool
pitch. The Action's contact_made is displacement-floor based, not a contact sensor.
No positive post-last-contact free-flight tail appears in the audited execution
windows; that does not exclude impact forces while contact persists.

## New preregistered geometry pair

Fixed order G0 then G1; same exposed seed2000, image/world, maximum three attempts,
30 mm request, 5 mm overdrive, one increment, demo_slow and frozen grading.
Only the world EE-height request differs. No infrastructure failures/replacements.

| Run | EE target height | Final net forward | Primitive contracts | Full task |
| --- | ---: | ---: | --- | --- |
| G0 | 20 mm | +106.664 mm | 0/2; under-delivery then overshoot | PASS, 9/9 |
| G1 | 55 mm | 0.000 mm | 0/3; no native contact during strokes | FAIL |

G1 fails terminal/pusher_contact. Its raw verifier evidence_status is
INCOMPLETE_OR_INVALID_EVIDENCE, physical_outcome UNKNOWN; trajectory and other
gates pass. This is an executed zero-motion failure, not a missing-log replacement.
Its fixed TCP-height proxy did not meet the preregistered mechanism gate; no
repetition batch was earned. Default EE height remains 20 mm. No claim about all
possible geometry corrections follows from this one rejected configuration.

The conditional speed pair was replaced before execution, as recorded in
`GEOMETRY_PILOT_PREREGISTRATION.md`; it is NOT_RUN. New profile/height CLI fields
make the experiment explicit and preserve defaults, without touching the core.

## Initial-world repair

New `scripts/task_world.py` provides materialize / verify CLI and Python functions.
It accepts public initial object declarations, preserves non-pose world properties,
supports existing same-size box models and refuses unsupported/missing geometry,
relative frames and malformed declarations. It only creates a new world before
launch; no live pose-setting or TaskSpec modification occurs.

`initialization_probe/` is explicitly synthetic **infrastructure validation**.
Two changed xyz/yaw poses materialize in Gazebo with about 2.5e−9 m position error
and floating-point yaw error. The old default dev coordinates are rejected.
There are no PushObject/MoveToPose task goals. No robot task is graded or counted.
The CLI reproduces the Gazebo-verified world's exact bytes, accepts its measured
initial truth and rejects the wrong world. Eight initializer checks pass.

`executed_sources/` retains the exact initializer/probe source used in Gazebo.
The subsequent CLI addition does not change those algorithm ASTs, and its output
matches the measured world byte-for-byte. `integrity_after.json` records this
distinction instead of claiming the later CLI itself ran in the earlier process.

The historical specialized runners remain unchanged. The new module is a usable
initialization seam; unified runner integration and unseen manipulation remain
future work. Initial-world correctness is not a robot manipulation capability.

## Other architecture findings and limits

The Runtime composite route already has native PUSH, while its decision menu
and new feedback CLI are not connected. Primitive result poses precede retreat;
retreat_failed is logged but absent from the ROS result type. The composite's
existing post-observation guards should be retained, not bypassed. The engineering
CLI's expected_goal input is not an Agent public-input boundary.

A synthetic proposal-generator check reproduces re-generation of an already
superseded release-retry idea. Its prevention is assigned to
[#236](https://github.com/Yenefa/flexcell/issues/236); no proposal was applied.
The old carry-ack-only success proposal is not adopted; carry belief is not
independent physical release evidence. Ordinary pick/place was not rerun this
turn; previous failed and passed normal smokes remain distinct.

95 existing relevant unit checks, five coordinate checks, eight initializer checks
and four synthetic real-ROS protocol checks passed. These are software checks,
not robot task counts. No Agent self-report was supplied: False Success rate and
claim accuracy remain NOT_MEASURED. No confirmed gate false rejection in this pair.

Nine frozen files, push core and nine related motion/release modules are unchanged;
the exact geometry-pilot source hashes match preexecution. No core/interface/
threshold or shared-install changes, held-out task, paid model, hardware, PR,
main merge, release or formal baseline promotion. T08 remains
CALIBRATION_UNSUPPORTED; Runtime-autonomous L4 NOT_ACQUIRED.

## Replay

`raw_runs.zip` retains all new raw runs/checks, hash-verified by
`raw_runs_sha256.json`. Read-only summary, after extraction to a fresh directory:

```sh
python3 setup/acceptance/evobot_contact_arch_audit_20261112/summarize_audit.py /path/to/extracted
python3 setup/acceptance/evobot_contact_arch_audit_20261112/audit_contact.py /path/to/extracted G0 G1
```

To reproduce the retained old-data audit, separately extract the prior published
feedback archive and run `audit_contact.py` with B1 B2 B3 pilot2. No simulator or
model call is used for these read-only replays.
