# T08 calibration — capture-link probe result (2026-11-12)

## What was tested

`sim_profile.profile(..., camera=True, ...)` + `trusted_sim.launch.py camera:=true`, one stack start, no policy,
no grading. Purpose: confirm the **visual capture link** exists before spending the calibration budget.

## Result — the link works

```
profile OK (camera=True)      world.sdf contains dataset_camera x1
stack up: 1                   push_object action server reachable
image topics:
  /flexcell/camera/rgb
  /flexcell/camera/rgb/camera_info
```

| item | status |
| --- | --- |
| camera plugin (`gz::sim::systems::Sensors`, ogre2) | **present and rendering** — world.sdf carries `dataset_camera` |
| ROS image topic | **`/flexcell/camera/rgb`** (plus `camera_info`) |
| resolution / format | **640×480 RGB** (`R8G8B8`), near 0.02 / far 3.0 — per `sim_profile` |
| model load impact | none observed; `push_object` came up normally with the camera enabled |
| clean shutdown | yes, no processes left |

## Why this matters for the calibration

The human required **real visual records** of the calibration, not inferred ones. Until now every T08 run in this
repository ran `camera:=false`, so **no T08 experiment has ever had a photograph attached to it.** This probe
establishes that adding one needs no change to the simulator — only subscribing to `/flexcell/camera/rgb` and
writing PNGs, which is capture-side work.

## Not yet done

- **no image has been saved to disk yet** — this probe only confirmed the topic exists and publishes
- the Agent **decision log** is still not recorded anywhere; that is new instrumentation, not existing plumbing
- contact **force** is not currently exported by the evidence bundle

**Next**: wire PNG capture to `/flexcell/camera/rgb` plus a decision log, then run the small batch (3–5) that the
human required before any scaling to 60.

## T08 calibration — value tag

**V3 (experimental trustworthiness) + V2 (key capability)**: the gripper gate currently rejects physically correct
pushes; without calibration no T08 pass rate in this repository can be interpreted. This is the only
P1-class task on the critical path, and it is human-approved with the threshold frozen.
