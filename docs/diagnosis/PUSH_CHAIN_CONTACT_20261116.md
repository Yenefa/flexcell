# Push chain: contact measured, five declared attempts (2026-11-16)

The carry backends cannot produce a contact-force statement: `contact_force_observed`
was false in every pick/place row this session. The push chain is where contact is
actually measured, so that is where a physical conclusion had to come from.

This page records what was run, what the engine measured, and what is still not
established. Nothing here changes the `detachable_joint` decision, which remains
`NO_GO_FOR_DEFAULT_ADMISSION` (see `CARRY_BACKEND_PHYSICAL_20261116.md`).

## Setup

The push adapter (`src/flexcell/flexcell_skills/run_contact_push.py`) needs three
things that are not obvious, and all three cost a failed run to find:

1. **A model directory with `robot.urdf`.** `ContactGeometry` parses the arm's
   joint origins and one binary collision mesh per link. CI ships this at
   `/artifacts/model`; it is not in the repository. Built it from
   `open_manipulator_description`:

   ```
   xacro open_manipulator_x.urdf.xacro use_sim:=true  -> robot.urdf
   cp meshes/open_manipulator_x/*.stl                 -> model/
   ContactGeometry OK: 7 meshes, 8 sources
   ```

2. **Trace files at `out.parent`, and they must not exist yet.** The native plugins
   take their destination from `FLEXCELL_PHYSICS_STEP_LOG` / `FLEXCELL_CONTACT_STEP_LOG`.
   Pointing them at a path that already exists makes gz abort at startup with
   `physics step log already exists`, and the symptom is not an error in the log
   the caller reads - it is `/joint_states` silently never appearing.

3. **The adapter must start before the physics stream is deep.** `NativeContact`
   keeps a 4096-frame window and reads each tail from offset 0 on its first poll.
   Starting the adapter 50 s after the simulator means the first poll swallows
   ~25,000 rows, evicts most of the window, and then every older contact row is
   refused as `native contact step expired without a physics match`. `fresh()`
   latches that error and returns False forever, which surfaces as
   `MotionFailed: fresh complete measured joints unavailable`. Starting the
   adapter as soon as the traces appear removes the backlog.

The task must also match the world's default placement. `T08-push-seed3000`
declares the box at `(0.21, 0.03, 0.0175)` while `sim_profile` places it at
`(0.22, 0, 0.0175)`; the 1 cm difference is refused as
`initial scene differs from declared task`. The `t08_fresh_zone_20261112` tasks
declare the default poses and do run.

Configuration: `detachable_joint` + `physics_step_s = 0.002` +
`contact_trace = True` (enforced by `sim_profile.profile`), task
`benchmark/tasks/t08_fresh_zone_20261112/T08-push-seed5000.json`, `--attempts 1`.

## Results

| run | status | actuator goals | net stroke | contact observed | contact steps |
| --- | --- | --- | --- | --- | --- |
| 1 | STATE_UNAVAILABLE | 0 | - | - | - |
| 2 | GOAL_GEOMETRY_REACHED | 12 | 30.4902 mm | **true** | 8,169 |
| 3 | STATE_UNAVAILABLE | 0 | - | - | - |
| 4 | GOAL_GEOMETRY_REACHED | 12 | 30.4921 mm | **true** | 7,919 |
| 5 | GOAL_GEOMETRY_REACHED | 12 | 30.4929 mm | **true** | 8,086 |

For the three runs that reached the goal, the native monitor recorded, from the
engine's own contact stream at 2 ms:

| quantity | run 2 | run 4 | run 5 |
| --- | --- | --- | --- |
| `rear_fraction` | 1.0 | 1.0 | 1.0 |
| `horizontal_normal_fraction` | 1.0 | 1.0 | 1.0 |
| `maximum_patch_distance_m` | 1.41e-05 | 1.70e-05 | 1.53e-05 |
| `unexpected_robot_colliders` | [] | [] | [] |
| `protected_peak_m` | 3.98e-10 | 3.98e-10 | 3.98e-10 |

The primitive receipt for each says `primitive_outcome: SUCCEEDED`,
`requested_m: 0.03`, `stroke_signed_m: 30.49 mm`, `physical_contact_observed: true`,
`motion_terminal_known: true`.

**What this establishes.** In this world, on this host, the finger really touched
the box: the engine reported contact on 7,919-8,169 two-millisecond steps, every
one on the registered rear patch (fraction 1.0), with normals horizontal
(fraction 1.0), the touching surface within 14-17 um of where the registration
says it is, no unexpected robot collider in the stream, and the protected object
displaced by 4e-10 m - i.e. not at all. The stroke moved the box 30.49 mm where
30 mm was asked. That is a measured physical statement, not a claim read back
from the planner.

**What this does not establish.** Three of five reached the goal, so this is not a
success rate and must not be quoted as one: the other two failed before any
motion was dispatched (`actuator_goals: 0`) on the startup race described above,
which is an orchestration defect in my harness, not a physical failure. All three
successful runs are the same task at the same seed; nothing here says the policy
generalises. `independent_acceptance_claim` is false in every run - the adapter
does not certify its own success. And these are contact facts about a 35 mm box on
a table under `detachable_joint`+2 ms, not about the default admission profile.
