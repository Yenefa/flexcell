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

The implementation check passed **550 tests, no errors/failures/skips**.
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

The completed receipts are in [the evidence archive](../setup/acceptance/trusted_sim_20261027/README.md):

- The first five-case core window retains STOPPED because strict JSON reporting rejected
  the expected budget failure's NaN distance after cleanup. A separate raw fact audit
  verifies A, B, dual-object, once recovery and the expected budget failure with clean
  health. Six adversarial mutations are rejected. No replacement trials were run.
- The corrected, declared data window passed with three successful tasks and two retained
  failed tasks. The official LeRobot writer/loader verified **5 episodes / 574 frames**,
  including all four source timestamps. The [complete sample](../data/examples/trusted_sim_20261027/README.md)
  is committed. A one-second recorded context surrounds each task; unmeasured result
  distances become null with explicit unavailable-field metadata, never zero.
- Three native attachment cycles passed release/reattach, cross-object ownership, rejection
  of retired releases/re-engage, and heartbeat expiry (observed about 0.471 s from the
  timestamp recorded after stopping/joining the heartbeat worker, not from the exact
  final heartbeat reply). The isolated worker exited 0 and final health was clean.
- Two actual MTC motion fixtures passed mid-motion cancellation and deadline expiry.
  Both confirmed controller termination, measured stop and preemption before the planned
  endpoint. These fixtures and the native lifecycle fixture now run in PR simulation CI.
- A separately declared two-task joint/MTC window passed A and B. All **462 / 429**
  attached synchronous samples were checked, with no transition samples removed: relative
  translation drift stayed below **0.8 micrometres**, orientation drift below **3.3 microradians**.
  Final placement errors were **24.7 / 19.9 mm**, within the existing 60 mm contract.
  This verifies these oracle fixtures; it does not establish contact-grasp reliability.
- The first GitHub-hosted full-stack [run](https://github.com/Yenefa/flexcell/actions/runs/40502091503)
  built from scratch, tested all four packages, ran legacy/MTC tasks and uploaded artifacts
  successfully in about 11 minutes. Later commits additionally include lifecycle fixtures.

Remaining work is tighter object-frame placement geometry, longer qualification only after
a new declaration, camera calibration/visual Observe, hardware and model comparisons.
Defaults stay unchanged pending that qualification. CameraInfo was not qualified in the
sample; RGB is a data-only stream. The optional 30-minute camera job is separate from
required core smoke. Required branch protection still needs repository administration
access; workflow files alone cannot enforce merge rules.

Against the stricter task-book criteria, current joint admission is explicitly
[NO_GO_FOR_DEFAULT_ADMISSION](DETACHABLE_ADMISSION_20261027.md): five non-contact cycles,
ten-second stability, contact/pre-positioning cases, elevated free fall and 500 Hz/contact
force checks are incomplete. The backend is an experimental spike, not an admitted default.
The five-task acceptance declaration is now executed by CI from the committed revision;
the earlier local STOPPED window remains a development record.

Subsequent CI retained two failures rather than retrying them: run 40539227821 stopped
at native startup health before any backend cycle; run 40537157656 completed its five
camera tasks but the data export rejected camera timestamp gaps. The latter produced no
new learning dataset. Their receipts are archived. Code review identified a bootstrap
dependency on ever observing the transient initial joint; readiness now requires current
detached physics over advancing steps and connected official command channels instead.
Additional native startup diagnostics are saved on failure. This candidate change passed
the local lifecycle fixture; the exact cause of the old CI failure was not directly
observed in its limited native-status logging. Admission remains NO_GO.

The implementation revision `05937ad` passed both [offline CI](https://github.com/Yenefa/flexcell/actions/runs/40542302649)
and [full-stack CI](https://github.com/Yenefa/flexcell/actions/runs/40542302631), with
550 tests and no errors, failures or skips. The latter completed in about 13 minutes
26 seconds, including the committed five-task velocity/MTC window: A, B, dual-object,
once recovery succeeded, and budget exhaustion failed as declared. The five tasks
shared one runtime fingerprint and all cleaned up. The native lifecycle and measured
MTC cancel/deadline fixtures passed too. The [receipt](../setup/acceptance/trusted_sim_20261027/ci-05937ad.json)
records exact declarations, results, artifact digest and retained prior failures.
The optional camera job was skipped on this revision; its earlier failed export remains
unresolved. This record changes neither joint admission nor the earlier STOPPED window.

Decision: [ADR-004](ADR/ADR-004-trusted-simulation-plane.md).
Portable commands: [REPRODUCE.md](../REPRODUCE.md).

## Resume partially completed tasks

Set the task server's `resume_completed_objects` parameter to `true` to enable
the same completion shortcut for FSM, Jev, LLM or Hybrid. After observing an
object at its assigned goal, the policy requests the independent verifier.
Only a successful measured verification skips that object's pick/place;
remaining assignments continue through the selected policy. A failed initial
check starts with a fresh observation and uses the existing verification budget.
The option defaults to false and records a distinct `<policy>+resume` identity.

Run the physical control with `gh workflow run sim.yml -f resume_smoke=true`.
Both arms use the same already-placed object, Joint/legacy skills and verifier.
The runner checks one pick/place in the reference arm and zero in the resume
arm, with one successful independent verification in each. This measures the
completion feature; learned-policy reliability, latency and cost remain separate.
