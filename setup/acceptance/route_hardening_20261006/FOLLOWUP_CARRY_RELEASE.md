# Follow-up: PLACE loses carry-release discovery

The first transport-hardening S1 batch retained a real failure in run 4,
`week1_demo_v1-f42be3f5`. PLACE_A was accepted, both approach motions
completed, but the PLACE participant could not discover
`/flexcell/carry_release` within its existing five-second deadline.

Evidence: `phase1/place.jsonl`, the failed episode under `phase1/episodes/`,
`phase1/skill_transport.jsonl`, and `phase1/fleet.log`.

- PLACE outcome: FAILED, error 25, motion error 0, released false.
- Exact detail: `carry release service unavailable; object remains attached`.
- The carry process logged engagement before this failure and release during
  the following reset. The frozen fleet log contains no carry-process exit.
- The same batch's following run completed both placements successfully.

The final runtime reproduced the same detail in run 4,
`week1_demo_v1-dc2980c5`, with error 25 and released false. Its records are
under `final/`. Final run 2, `week1_demo_v1-471252c7`, instead failed with
PLACE error 30 / motion error 22: `hover motion failed: no response from
controller action`. These are separate failure classes.

After the final batch, `123_place_dependency_probe.py` made five read-only
readiness queries in a short burst. Both external discovery and the PLACE
participant's own `/flexcell/place_ready` responses were ready for all five.
It issued zero carry-release calls and zero physical goals. This establishes
current recovery only, not historical availability or a fixed root cause.

The cause is **UNKNOWN**. These observations establish an intermittent
participant-level discovery failure; they do not establish process death,
physics failure, or a specific DDS/RMW defect. Increasing the timeout without
additional evidence would obscure the failure rather than identify its cause.

The next focused investigation should capture the PLACE client's service graph
and readiness at the failure instant, with monotonic timestamps and process
lifecycle records. A current external graph snapshot cannot reconstruct that
participant's past discovery state. Keep this failure separate from the
original OBSERVE_B SendGoal timeout and from controller-action response loss.

No issue has been published, no failure replaced, and no large batch started.
