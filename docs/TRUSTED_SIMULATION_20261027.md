# Trusted simulation implementation, 2026-10-27

This implements the first technical upgrade plane from the route audit. It does not
declare the three-month roadmap or contact/real-arm reliability complete.

PR [#51](https://github.com/Yenefa/flexcell/pull/51) is merged as `05c145d`.
Main [CI #79](https://github.com/Yenefa/flexcell/actions/runs/40497953065) passed.
The following components are developed in the subsequent implementation branch.

| Component | Implementation | Evidence boundary |
| --- | --- | --- |
| Historical facts | New fact checker with adversarial archive mutations | Ten old trials; mechanism UNKNOWN |
| Environment | Image digest, four ROBOTIS SHA pins, exact MTC versions | Four first-party packages built in Jazzy |
| Portable launch | Server-only first-party launch, generated world/params, import/source hashes | No required WSL user, F: staging or deployment overlay |
| DetachableJoint | Official systems with ownership/lease adapter | Initial smoke passed; placement geometry remains a qualification item |
| MTC | Planning-only C++ adapter, one-use handoff to shared MoveToPose executor | No new policy, recovery or controller owner |
| Physics trace | Synchronous parent/EE/A/B poses and joint-component state at 50 Hz sim time | Direct observations; service ACK alone is insufficient |
| Data | RGB, numeric states/controller references, accepted gripper targets, raw bag | Camera is data-only; Observe remains ground truth |
| LeRobot | Official v0.6.1 writer/loader, isolated CPU venv | Initial 142-frame roundtrip passed; no training or hardware replay |
| CI | Offline tests and headless legacy/MTC smoke, separate camera/data job | GitHub full-stack run and required-check administration tracked separately |

The initial implementation check passed **545 tests, no errors/failures/skips**.
Development smokes completed one velocity/legacy, one velocity/MTC and one joint/legacy
task, with independent verification and clean post-reset health. These are development
checks, not a reliability sample. Code/config changes receive new fingerprints.

The joint/legacy task finished with about 34 mm placement error, within the existing
60 mm tolerance. Fixed attachment rotates the full relative transform; the legacy place
path assumes a fixed world-vertical offset. This geometry needs qualification before a
default change. A task passing once does not establish backend reliability.

## Historical inference correction

The Phase-3 raw archive and its historical verifier remain unchanged. Current CI uses
`setup/verify_phase3_facts.py` instead of the old causal assertions:

- Ten declared trials: nine measured PICK successes, one error 23.
- 639 lookups, zero reported missing; 638/639 pin requests confirmed.
- Failed B5 trial 2: 45 lookups, zero missing, 45 confirmed pins, rise 0.023416 m.
- Clean recorded before/after health. TF freshness, sustained physics, the failure
  mechanism and commonality with historical negative-rise failures remain UNKNOWN.

Endpoint residuals were not simultaneous observations. The observed 71.7 mm residual
is not a physical upper bound. Earlier velocity-reset experiments remain relevant;
they do not prove the cause of every failure in another cohort.

## Windows and provenance

`infra/core-window.json` declares A, B, dual-object, once recovery and budget exhaustion.
`infra/data-window.json` declares three normal examples, unreachable place and budget
exhaustion. `scripts/sim_window.py` executes each declaration once and stops without
replacement on a gate failure. Expected failed tasks retain their failed outcome.
Unknown child motion forbids reset or further dispatch.

Runs store imported/source digests, native binary digests, dependency manifest digest,
semantic config fingerprint, action UUIDs/results, skill/motion logs, raw bag, physics
traces and cleanup health. MTC stage tokens/trajectory hashes join skill evidence to
actual motion action evidence. Output paths are excluded from semantic fingerprints.
The scenario order and initial poses are fixed; planner/scheduling determinism is not claimed.

Export rejects missing aligned data and camera gaps rather than selecting a good subset.
LeRobot's standard timestamp is `frame_index/10`; original camera/state/reference/gripper
simulation stamps remain int64 features. Official loader readback checks all source
stamps, numeric state/actions, frame/episode counts and decoded video shape.

## Remaining gates

1. Finish declared windows and publish exact receipts, including NO_GO outcomes.
2. Qualify repeated joint attachment, release, ownership, expiry and relative-transform
   stability; resolve rigid-attachment placement geometry.
3. Confirm GitHub-hosted runtime, duration and failure artifacts. Required branch protection
   needs repository administration access; workflow files alone cannot enforce merge rules.
4. Qualify MTC cancel/timeout/recovery parity before making it default.
5. Keep perception, hardware and model comparisons outside this window.

Decision: [ADR-004](ADR/ADR-004-trusted-simulation-plane.md).
Portable commands: [REPRODUCE.md](../REPRODUCE.md).
