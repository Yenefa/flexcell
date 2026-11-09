# CPU-class place deadline — 2026-11-09

> Local adaptation record. It changes `semantic_config_sha256` and the runtime
> fingerprint, so any host adopting this config must re-run acceptance. It is not
> a claim that 60 s is correct for the reference delivery host.

## Scope

`src/flexcell/flexcell_skills/config/week1.yaml`:

```yaml
place_server:
  ros__parameters:
    default_deadline_ms: 60000   # was 30000
```

Revert by restoring `30000`. Nothing else changed: no source logic, no interface,
no world, no skill contract.

## Host class

| Item | Value |
| --- | --- |
| Host | Core i7-13620H, 16 GB, Windows 11 26H2 |
| Runtime | WSL2 `Ubuntu-24.04` (imported rootfs), mirrored networking |
| Allocation | 12 vCPU / 10 GB, swap 4 GB |
| ROS | Jazzy `ros-base` (362 packages), `gz-harmonic 8.15.0`, `moveit 2.12.4` |
| MTC | `0.1.8-1noble.20260915.205448` (repo-pinned version) |
| Rendering | CPU only (`llvmpipe`, headless; `DISPLAY` unset) |

## Observed failure

Window `983927a0…`, trial-01 (`normal` / `target_box_a`), first dispatch:

```
place.jsonl: status=2 error_code=30
  "MTC planning failed before execution: planning reply timed out; no motion dispatched"
task_fsm:    policy abort (NON_RECOVERABLE): place failed (ERR_MOTION_FAILED ...)
```

Pick was healthy in the same task (`picked target_box_a: attached, measured rise
0.099 m`). `stack.log` shows `mtc_planner` emitting its MoveIt model/kinematics
initialisation lines at the moment the request timed out:

```
[mtc_planner-13] Could not identify parent group for end-effector 'end_effector'
[mtc_planner-13] Joint weights for group 'arm': 1 1 1 1
```

`mtc_motion.prepare()` waits `deadline_ms/1000 + 8`, and clamps the request
deadline to 60 s. With `default_deadline_ms: 30000` the window was 38 s, which the
lazy first-request initialisation of the MTC planner exceeded on this CPU class
while Gazebo, MoveIt and six skill servers were contending for 12 vCPUs.

This is a cold-start cost, not a trajectory-planning failure and not a physics or
carry regression. `CarryDynamics` acknowledged-timeout warnings appear in both
failing and passing runs and are not a discriminator.

## Evidence after the change

All three windows: `status: FUNCTIONAL_WINDOW_PASS`, `no_replacements: true`,
identical runtime fingerprint
`f156d24ae74285335acbd0fa5f97cc67bc16cd7ed5aecbd98fffbb1eb3a7f324`.

| Window | `normal` A | `normal` B | `dual_object` | `recovery_once` | `budget_exhaustion` |
| --- | --- | --- | --- | --- | --- |
| `6064efcf…` | 0.058 mm | 0.059 mm | ok (32.9 s) | 0.089 mm | expected `ERR_RECOVERY_EXHAUSTED` |
| `8bc6cbc6…` | 0.061 mm | 0.068 mm | ok (32.7 s) | 0.113 mm | expected `ERR_RECOVERY_EXHAUSTED` |
| `1739611b…` | 0.068 mm | 0.134 mm | ok (32.9 s) | 0.071 mm | expected `ERR_RECOVERY_EXHAUSTED` |

`recovery_once` exercised the real seam in every window: `PICK_A(attempt=1):FAIL:ERR_GRASP_FAILED`
→ `RECOVERY:REOBSERVE+RETRY` → `PICK_A(attempt=2):OK` → `PLACE_A:OK` → `VERIFY_A:OK`.

The stock 30 s config produced fingerprint `6cc8ca51…`; a single-task
`sim_smoke` on that config passed with 0.112 mm, so the stock value is not
universally broken — it fails when the planner's first request lands under load.

## Boundaries

- Functional window only. `n >= 50` stays frozen; these three windows are not a
  success-rate estimate and must not be quoted as one.
- No claim about the reference delivery host, whose GPU-backed rendering and
  warmer page cache were not reproduced here.
- `budget_exhaustion` is expected to fail; `expectation_met: true` is the gate
  accepting a retained typed failure, not a pass of the task itself.
- Camera path, policy backends (`jev` / `llm` / `hybrid`) and LeRobot export were
  not exercised on this host.
