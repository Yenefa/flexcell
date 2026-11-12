# Safe reposition adapter — preregistered development probe

Base `fa08d8fe`; unchanged runtime/evaluator ancestry `30fa2066`.
No old evidence, frozen core push contract, TaskSpec or acceptance limit is edited.

## Hypothesis

Observed reverse motion during successful low retreat/re-approach can be reduced
by explicitly lifting before lateral return, with measured clearance checked before
transit. A successful MoveToPose at contact height is not sufficient evidence.

## Geometry and limits

Pinned upstream STL vertices and URDF joint limits give maximum tool radius about
EE = 0.14779145321586976 m for link5 and both gripper collision meshes.
For a 0.035 m object top and 0.005 m geometric margin, required measured transit
EE z = 0.18779145321586976 m. Commanded height adds the unchanged 0.020 m
tracking tolerance: 0.20779145321586975 m. Keep the mesh identities and calculation.
This bound covers the tool assembly, not the forearm or continuous swept path.

## Minimum experiment

1. Pure/interface tests must show no horizontal transit after failed lift,
   insufficient measured height, stale/unavailable EE state or cancellation.
2. One original control and one opt-in candidate, separate fresh Gazebo instances,
   dev seed2000, contact height 0.0200 m, target 0.0900 m, at most two PushObject
   requests. The control uses original installed source; the candidate uses a
   read-only Python source overlay. Same container image and materialized world.
3. Keep full Push, MoveToPose, WorldState/phase, initial/final simulator truth,
   source identities, result files and the unchanged independent evaluator output.
   Every materialized node log_dir is explicit, including Push. No broad pkill.

Before executing either arm, acquisition is extended with identical observational
ContactTrace/sensors in both copied worlds and synchronous native step logs.
Physics timestep, masses, friction, robot and task poses stay unchanged. Joint
states are recorded directly. The existing recorder binds rest height to the
TaskSpec, and the existing evaluator receives that bundle plus max_z recomputed
from raw physics samples. No changes to recorder/evaluator acceptance logic.
Pusher collision names are declared from the pinned URDF before inspecting results:
link5, gripper_left_link and gripper_right_link under open_manipulator_x.

## Decisions fixed before execution

- Mechanism supported only if actual waypoints occur in order, actual lift/transit
  endpoint height meets the declared bound, and return-induced red backslide is
  no more than the existing 5 mm displacement tolerance, with no protected-object
  displacement or observed carry. This is an intermediate engineering gate;
  it never replaces frozen full task acceptance.
- A failed lift or motion stops that route. No low horizontal shortcut or extra
  retry is allowed to manufacture a favorable result.
- A negative result is retained. Do not pool this pair with the earlier nine or
  the earlier observation-only run. No success-rate/generalization claim at n=1.
- Full task capability remains unsupported without the complete physics/contact
  bundle and all independent acceptance gates. Report gripper issues separately.
- If this waypoint strategy fails, locate the failing waypoint and actual path
  before proposing a different candidate; no same-configuration repeat batch.
