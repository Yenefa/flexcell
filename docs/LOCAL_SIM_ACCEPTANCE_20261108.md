# Local ROS/Gazebo acceptance capability — 2026-11-08

Status: **works on the delivery desktop, natively in WSL, no Docker.** This records the
capability and one smoke result each for the plain and camera paths. It is not a new
benchmark qualification and not the U3 composite acceptance.

## Host
- Windows 11 desktop, WSL2 Ubuntu 24.04; 12 cores / 15 GB RAM / 919 GB free.
- No `/dev/dri` (no GPU passthrough). Rendering uses Mesa **llvmpipe** through EGL surfaceless:
  `OpenGL 4.5 (Core Profile) Mesa 25.2.8`, `GLES 3.2` — the same software path the CI image uses.
- ROS 2 Jazzy, `ros-jazzy-gz-sim-vendor` (gz-sim 8.15.0), `ros_gz_bridge/sim`,
  `ros2_control` + controllers, MoveIt 2, CycloneDDS and the gz Python bindings are installed.

## Build
- Source: current `main` (`a020f23`) extracted to ext4; 4 packages built with
  `colcon build --merge-install --parallel-workers 6` in **2m22s**.
- Upstream ROBOTIS stack reused from the existing `~/agentic_workcell_ws` install.
  **Caveat:** that checkout is `6c563fd`, not the pinned `17efe42` from
  `infra/upstream.lock.repos`, because GitHub fetches from WSL were timing out. A locked
  re-run is required before calling any result provenance-complete.

## Smoke results
| Case | Result | Placement error | Wall | Runtime fingerprint |
| --- | --- | --- | --- | --- |
| `sim_smoke` velocity_servo / normal / target_box_a (no camera) | **PASS**, OUTCOME_SUCCEEDED, PICK_A/PLACE_A/VERIFY_A all OK | **0.514 mm** | 15.9 s | `bccc9338…f96501` |
| same + `--camera` | **PASS**, OUTCOME_SUCCEEDED | **10.85 mm** | 22.8 s | `45daaaa0…c5285b` |

Camera path detail: 442 frames in `frames.jsonl`, 296 written live (209 valid), and
`reconcile` status **RECONCILED** with **146** frames backfilled from the rosbag (expected 486).
The slow software renderer drops more live camera frames than CI does, so this is a stronger
load test of the rosbag-reconcile fix (#128/#130) than the CI camera-data runs.

## What this unlocks
- U3 (composite runtime integration) can now be rebased and exercised with a real ROS/Gazebo
  window **on this machine**, with a new fingerprint, instead of waiting for an external host.
- Remaining gap for a provenance-complete acceptance: align the upstream checkout to
  `infra/upstream.lock.repos` (network permitting) and re-run the same smokes.

## Non-claims
No success rate, no n>=50 unfreeze, no composite/U3 acceptance, no AC@90 claim.
