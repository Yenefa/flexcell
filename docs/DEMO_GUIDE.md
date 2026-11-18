# Demo guide — continuous pick-and-place with a GPU GUI on WSL

How to bring up the trusted simulation, open the Gazebo window, run the two-object
`/run_demo` cycle, and record it. Commands are copied from the in-tree scripts where a
script exists; anything not verified in this repository is marked **TODO**.

Reference session: `scripts/demo_session.sh` (stack + GUI + ffmpeg + two cycles).

## 0. What one demo is

One `RunDemo` goal is the continuous scene:

```
OBSERVE_A -> PICK_A -> PLACE_A -> VERIFY_A -> OBSERVE_B -> PICK_B -> PLACE_B -> VERIFY_B
```

`target_box_a` goes to `zone_1 (0.12, -0.15, 0.0175)` and `target_box_b` to
`zone_2 (0.25, 0.05, 0.0175)`; both come from the server parameters, not the goal
(`task_fsm_server.py:205-212`,
`src/flexcell/flexcell_skills/config/week1.yaml:101-108`). Recovery is bounded by
`recovery_budget` (default 1), so a recoverable failure gets one `REOBSERVE` + retry.

Both objects count as at their zones only when their VERIFY stage measured them inside
`demo_verify_tolerance_m` (0.06 m in
`src/flexcell/flexcell_skills/config/week1.yaml`). What a run must show to be
*accepted* (artifact layout, delta gate, exit codes) is in
`docs/ACCEPTANCE_INTERFACE.md` §4-6.

## 1. Environment: GPU GUI inside WSL

Export these in the shell that launches the stack, and again in any terminal that
runs a client:

```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=45
export GZ_PARTITION=pp-manual
export GALLIUM_DRIVER=d3d12
export MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
unset LIBGL_ALWAYS_SOFTWARE
```

- `GALLIUM_DRIVER=d3d12` plus `MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA` is the
  GPU path used by the demo script (`scripts/demo_session.sh:23`). On the host where
  this was diagnosed (AMD RX 6800), WSLg's XWayland had no DRI3, Mesa fell back to
  llvmpipe, and the GUI burned 164% CPU (72% after the fix) with the carry servos
  starving (`docs/HANDOFF.md:322-323`).
- `unset LIBGL_ALWAYS_SOFTWARE` matters because several batch scripts export
  `LIBGL_ALWAYS_SOFTWARE=1` for headless runs (e.g.
  `setup/acceptance/evobot_t08_first_run_20261111/evobot_t08_push_first_run.sh:67`).
  A shell that inherited it will stay on the software path.
- **Vendor caveat:** `REPRODUCE.md:144-152` records that `GALLIUM_DRIVER=d3d12` is
  AMD-specific and is no longer exported by `setup/flexcell`. The d3d12 path is the
  one this guide's script uses; on a host where it does not help, fall back to
  `LIBGL_ALWAYS_SOFTWARE=1` and expect the CPU cost. TODO: record which GPU vendor
  each demo machine uses.

### `GZ_PARTITION` must match everywhere

`GZ_PARTITION` is the Gazebo transport partition. The server, the GUI and any
`gz topic` call have to use the same value; `docs/ROS_MCP.md:302` states the same rule
for multi-terminal work and for isolating one Gazebo world from another. A GUI on a
different partition cannot see the server's world.

| Session | Partition |
| --- | --- |
| scripted demo (`demo_session.sh`) | `pp-demo` |
| manual session (this guide) | `pp-manual` |
| concurrent window slot | `pp-<label>`, one label per slot |

The only one of these values that appears in the tree is `pp-demo`
(`scripts/demo_session.sh:22`). `pp-manual` / `pp-<label>` are the team convention for
manual and window-slot sessions. TODO: codify the label rule in the launcher.

`ROS_DOMAIN_ID` and `RMW_IMPLEMENTATION` must match as well, or `ros2 action list` in
the second terminal will be empty even though the stack is healthy.

## 2. Get a world file and a params file

The launch file takes one world file and one params file, both required
(`trusted_sim.launch.py:118-121`). Generate a fresh pair:

```bash
python3 scripts/sim_profile.py --out /tmp/demo-profile \
  --backend velocity_servo --skill-backend legacy
```

It prints `{"params": ".../params.yaml", "world": ".../world.sdf"}` and refuses to
overwrite an existing pair (`scripts/sim_profile.py:253-257`, `:295-296`), so use a
new directory each time.

You can also reuse a completed run directory that already contains `world.sdf` and
`params.yaml`; that is what `demo_session.sh` expects (`scripts/demo_session.sh:5-14`).

## 3. Start the stack (terminal A)

```bash
source /opt/ros/jazzy/setup.bash
source install/setup.bash

ros2 launch flexcell_skills trusted_sim.launch.py \
  world:=/tmp/demo-profile/world.sdf \
  params_file:=/tmp/demo-profile/params.yaml \
  camera:=false
```

`world` and `params_file` are required arguments; `camera` defaults to `false`.

What this starts: the Gazebo server only (`gz sim -s -r -v 2`, no GUI —
`trusted_sim.launch.py:69`), the robot spawn, `joint_state_broadcaster` plus
`arm_controller` / `gripper_controller`, MoveIt without RViz
(`trusted_sim.launch.py:86-89`), and the skill servers from
`launch/week1.launch.py` (observe, pick, place, verify, task_fsm, carry, push).

Wait until the demo action exists:

```bash
ros2 action list | grep /run_demo
```

`demo_session.sh:39-43` polls exactly this for up to 120 s and exits nonzero if the
action never appears. Also expect `/run_pick_place` and `/verify_object`.

## 4. Open the window (terminal A or B, same environment)

```bash
gz sim -g
```

`-g` starts the GUI only and attaches to the running server through
`GZ_PARTITION` (`scripts/demo_session.sh:46`). The script sleeps 10 s after this
before recording.

If the window is empty, the partition differs from the server's. Close it, re-export
`GZ_PARTITION` and try again; do not start a second server.

### Camera framing

`~/.gz/sim/8/gui.config` stores the default view as:

```xml
<camera_pose>x y z roll pitch yaw</camera_pose>
```

**Roll comes before pitch and yaw.** Putting a yaw value in the roll slot tilts the
whole horizon by that angle; on 2026-11-18 `0.785` produced a 45-degree tilt in the
recording. A framing that shows the workcell from the front-left with a level
horizon:

```xml
<camera_pose>-0.6 -0.6 0.6 0 0.45 0.63</camera_pose>
```

Back up the file first, and restart `gz sim -g` after editing: the GUI reads
`gui.config` at start.

## 5. Run the demo

Continuous client, one goal:

```bash
python3 src/flexcell/flexcell_skills/test/w1_client.py \
  --action demo --scenario week1_demo_v1
```

Or the cycle runner, which sends one goal per cycle, resets the scene between cycles
and writes one `result.json` per cycle:

```bash
python3 scripts/run_demo_cycles.py --out "artifacts/demo-$(date +%Y%m%d-%H%M%S)" --cycles 2
```

Result fields that matter on screen and in the artifact
(`run_demo_cycles.py:87-100`):

| Field | Meaning |
| --- | --- |
| `outcome` | `0` SUCCEEDED, `1` FAILED, `2` CANCELED |
| `object_a_at_zone`, `object_b_at_zone` | `true` only when that VERIFY measured the object inside tolerance |
| `zone_a_error_m`, `zone_b_error_m` | measured distance to the zone; `NaN` means not measured |
| `duration_s` | wall time for the cycle |
| `evidence_id` | id of the task-level evidence record |
| `fsm_trace` | e.g. `PICK_A(attempt=1):OK`, `VERIFY_B(attempt=1):OK` |

`NaN` is "not measured". Never read it as zero error
(`docs/PICK_PLACE_RELIABILITY.md:77-78`).

Between cycles the runner calls `python3 setup/flexcell_admin.py reset` and requires
`"ok": true` in its output (`run_demo_cycles.py:38-43`). Without that reset the next
cycle starts from wherever the boxes were left.

Cancel path: `scripts/cancel_integration.py --out FILE` sends `/run_demo` and cancels
it mid-skill; it also proves the arm quarantine
(`cancel_integration.py:1-10, 30`). After a quarantine, `/flexcell/task_state` reads
`QUARANTINED` until `/reset_motion_quarantine` succeeds.

## 6. Record the screen

**On WSLg, `x11grab` cannot see the Gazebo window.** WSLg renders application
windows as Wayland surfaces; `ffmpeg -f x11grab -i :0` captures the empty XWayland
root and writes a black frame (measured 2026-11-18: `YAVG=16.0`, `SATAVG=0`). The
`x11grab` path in `scripts/demo_session.sh:49-63` is a fallback for a real X11
session only.

Record from the Windows host and crop to the Gazebo window:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/record_gazebo.ps1 `
  -SourceRun /tmp/carry-window3/out/NORMAL_1/run-7c231a57a747 `
  -Out D:\demo\gazebo.mp4 -Seconds 60 -Cycles 1
```

The script:

1. starts `scripts/demo_serve.sh` in WSL (stack + software-rendered GUI),
2. waits for `/tmp/demo-ready`,
3. finds the window titled `Gazebo Sim`, maximizes it, reads its client rectangle,
4. records exactly that rectangle with Windows `gdigrab`,
5. runs `scripts/run_demo_cycles.py`,
6. stops ffmpeg after its fixed duration and prints `ffprobe`.

Manual equivalent once the window is up:

```powershell
ffmpeg -f gdigrab -framerate 30 -offset_x <x> -offset_y <y> `
  -video_size <w>x<h> -i desktop -t 60 -c:v libx264 -pix_fmt yuv420p demo.mp4
```

- `-offset_x`, `-offset_y` and `-video_size` come from the window's **client**
  rectangle (`GetClientRect` + `ClientToScreen`), not the outer frame, so the title
  bar and the desktop are not recorded.
- If the D3D12 GUI segfaults in the NVIDIA driver (seen 2026-11-18), start the GUI
  with `LIBGL_ALWAYS_SOFTWARE=1` and unset `GALLIUM_DRIVER` /
  `MESA_D3D12_DEFAULT_ADAPTER_NAME`. `scripts/demo_serve.sh` does that.
- Verified output on this host: 1536x816, 30 fps, 60 s, one full `RunDemo` cycle
  (6/6 steps OK), level horizon, robot and both boxes inside the frame.

## 7. Output layout

`demo_session.sh` defaults `OUT` to `artifacts/demo-<timestamp>` with
`<timestamp> = %Y%m%d-%H%M%S` (`demo_session.sh:9`). A full `demo_session.sh` session
(stack + GUI + ffmpeg + two cycles) produces:

```
artifacts/demo-20261118-153000/
  demo.mp4                    # screen recording (top of OUT, written by ffmpeg)
  stack.log                   # ros2 launch output
  gui.log                     # gz sim -g output
  ffmpeg.log
  summary.json                # run_demo_cycles: cycles, passed, results[]
  cycle-1/
    result.json               # one RunDemo result record
  cycle-2/
    result.json
```

`cycle-<n>/result.json` is written by `run_demo_cycles.py:101-103`; `summary.json` at
the end (`:122-128`). Running `run_demo_cycles.py` alone produces the `cycle-*`
directories and `summary.json`, but not `demo.mp4` or the three logs. `artifacts/` is
gitignored (`.gitignore:15`), so the recording is a local artifact — copy it somewhere
durable before cleaning the tree.

These cycle files are **demo records**, not acceptance artifacts. `scripts/accept_run.py`
expects a runner result object (`status` + `task`) with `skills/place.jsonl` and
`skills/verify.jsonl` beside it; the mapping is in `docs/ACCEPTANCE_INTERFACE.md` §6.

Naming the session directory `demo-<date>` (as above) keeps cycles of one session
together; give each session its own directory rather than appending to an old one.

## 8. One command for the whole thing

On WSLg, use the Windows recorder from §6. It starts the stack, opens the GUI,
records only the Gazebo window, runs the demo and prints `ffprobe`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/record_gazebo.ps1 `
  -SourceRun /tmp/carry-window3/out/NORMAL_1/run-7c231a57a747 `
  -Out D:\demo\gazebo.mp4 -Seconds 60 -Cycles 1
```

On a real X11 desktop, `scripts/demo_session.sh [SOURCE_RUN_DIR] [OUT_DIR]` still
does the same in one shot. Two caveats: `SOURCE_RUN_DIR` must already contain
`world.sdf` and `params.yaml` (generate with §2), and it uses partition `pp-demo`
while the manual session in this guide uses `pp-manual`.

## 9. Troubleshooting

| Symptom | Likely cause | Check |
| --- | --- | --- |
| `ros2 action list` has no `/run_demo` | domain / RMW / partition mismatch, or the stack aborted | compare `ROS_DOMAIN_ID`, `RMW_IMPLEMENTATION`, `GZ_PARTITION` with terminal A; read `stack.log` |
| GUI opens but world is empty | GUI joined a different `GZ_PARTITION` | `echo $GZ_PARTITION` in both terminals |
| Goal returns `ERR_RESOURCE_BUSY (41)` | another task holds the arm lease | `/flexcell/task_state` should read `BUSY` |
| Goal returns `ERR_SKILL_FAILED (50)` with "motion quarantine active" | a previous stop was never confirmed | `/flexcell/task_state` reads `QUARANTINED`; call `/reset_motion_quarantine` only after checking the arm |
| GUI at ~100% CPU, servos stutter | software rendering | `GALLIUM_DRIVER` / `LIBGL_ALWAYS_SOFTWARE` as in §1 |
| ffmpeg "Cannot open display" | wrong `DISPLAY` or no X socket | `echo $DISPLAY`; re-run with that value |
| recorded video is black | `x11grab` cannot see WSLg Wayland windows | use `scripts/record_gazebo.ps1` (§6), check a frame's `YAVG` |
| horizon is tilted | `camera_pose` field order is `x y z roll pitch yaw`; a yaw value in the roll slot | set roll to 0 (§4) |
| GUI segfaults in `libnvwgf2umx.so` / `libd3d12core.so` | D3D12 driver path | start the GUI with `LIBGL_ALWAYS_SOFTWARE=1` (`scripts/demo_serve.sh`) |

## 10. TODO (unverified here)

- `pp-manual` / `pp-<label>` label naming is not in the tree; only `pp-demo` is.
- Whether `gz sim -g` fails cleanly or waits when no server is running on the
  partition; this guide only covers "server first, GUI second" (`demo_session.sh`
  order).
- GPU vendor per demo machine (see the `REPRODUCE.md` caveat in §1).

## 11. Evidence index

| Claim | Source |
| --- | --- |
| Env block, partition, GUI, ffmpeg, two cycles | `scripts/demo_session.sh:20-24, 35-46, 61-67` |
| Launch arguments and what starts | `trusted_sim.launch.py:50-94, 118-121` |
| Demo objects/zones/tolerance | `task_fsm_server.py:205-214`; `src/flexcell/flexcell_skills/config/week1.yaml:101-110` |
| Cycle artifact layout | `run_demo_cycles.py:87-103, 122-128` |
| Reset between cycles | `run_demo_cycles.py:38-43`; `setup/flexcell_admin.py:478-502` |
| Result field meanings | `flexcell_interfaces/action/RunDemo.action`; `task_fsm_server.py:960-990` |
| GPU diagnosis and numbers | `docs/HANDOFF.md:322-323`; `REPRODUCE.md:144-152` |
| Partition rule | `docs/ROS_MCP.md:302` |
| `NaN` = unmeasured | `docs/PICK_PLACE_RELIABILITY.md:77-78` |
