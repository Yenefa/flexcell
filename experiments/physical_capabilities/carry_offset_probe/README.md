# Carry-offset probe (issue #261) — local skeleton, not pushed

Read-only observation of **where the object sits in the gripper frame**, so the
placement spread in #247 can be split into grasp settling (lift), carry drift
(slip) and tracking error.

## What it reads

`observe_server` publishes `WorldState` **inside the `observe` action**, not on a
timer. A plain subscriber therefore sees a snapshot only at task decision points
(2-3 per slot), which cannot separate grasp settling from carry drift.

The probe sends one `observe` goal at a time (mode `action`, default) and consumes
the returned `WorldState`. Mode `topic` still subscribes, for setups that publish
periodically. It creates no publisher and no control service client; the only
outbound traffic is an observation request. If it dies, the task is unaffected.

`WorldState` carries both halves of the transform (`objects[].pose`,
`robot.ee_pose`), so `object_in_tcp = inverse(T_world_ee) * T_world_obj` needs no
TF subscription.

## Rows

`carry_offset.jsonl`:

```json
{"t_ns": 1760000000000000000, "event": "carry", "object": "target_box_b",
 "world_revision": 12, "source": "SIMULATION_GROUND_TRUTH",
 "object_in_world": [...], "object_quat_in_world": [...],
 "tcp_in_world": [...], "tcp_frame": "end_effector_link",
 "object_in_tcp": [...], "carry_session": "target_box_b",
 "backend": "velocity_servo"}
```

Events: `engage` (CarryState engaged turns true), `grasp` (one sample after
`--settle-s`), `carry` (20 Hz, one row per new revision), `release`.

- `source` is mandatory: simulation ground truth and hardware samples must never
  be mixed.
- The carried object follows `CarryState.object_id`, so `dual_object` sessions are
  recorded for both boxes instead of only the default label.
- Unusable snapshots go to `carry_offset_skips.jsonl` with a reason, never as a
  zero offset.

## Analysis

```bash
python3 analyze_carry_offset.py WINDOW_DIR [--out analysis.json]
```

Per carry session (the pairing key; one slot can have two):

| field | meaning |
| --- | --- |
| `engage_mm` | offset when carry engages (approach pose, gripper still closing) |
| `settled_mm` / `settled_event` | first sample whose world revision differs from engage, i.e. the held pose |
| `release_mm` | offset at release |
| `lift_mm` | engage → settled; grasp settling |
| `slip_mm` | settled → release; movement while carried |
| `delta_norm_mm` | engage → release, kept for the issue's table |

## Run

```bash
python3 probe.py --out /artifacts/carry-offset --object target_box_a --rate-hz 20
```

With the window driver, set `"carry_probe": true` in the preregistration; the probe
runs per slot in that slot's ROS domain and never fails the slot if it dies.

## Test

```bash
python3 -m unittest discover -s experiments/physical_capabilities/carry_offset_probe/tests -v
```

28 cases, no ROS, no simulator; geometry is also checked against
`flexcell_skills.pose_geometry`.

## Observed so far (descriptive, one host, one backend)

- Topic mode, four slots: 6 carry sessions (dual slots carry two boxes), all paired.
  Sampling was too sparse to separate lift from slip.
- Action mode, one slot: 42 samples, 39 revisions, `lift=12.5 mm`, `slip=10.5 mm`,
  landing `5.9 mm`. One slot is not evidence about the spread; it only shows the
  pipeline works end to end.

`object_in_tcp` is not constant during carry in these samples. Before concluding
"the object slides", check sample alignment and whether the requested baseline is
the held pose: that is what the `settled` field is for.
