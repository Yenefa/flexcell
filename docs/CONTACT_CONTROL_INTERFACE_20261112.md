# Finger contact, constrained motion and returned-state interface

Isolated development branch `develop/t08-contact-motion-20261112`, based on
6186271b. This interface is not the formal execution baseline or an autonomous
L4 claim. TaskSpecs, nine frozen files, `contracts/push.py`, gripper acceptance
and the existing MoveToPose server remain unchanged.

## Three concrete interfaces

`ContactGeometry.register_finger()` reads the exact simulation collision meshes
and URDF, composes the four-joint FK with both measured gripper positions, and
registers a point on an actual finger triangle. Its record includes TCP in
`end_effector_link`, triangle/plane patch, world support point and normal,
approach configuration, gripper state and source hashes. The virtual EE origin
and the STL bounding-box corner are not contact points. The current adapter
requires upright 35 mm boxes, a world -x stroke and the pinned robot geometry.

`ContactGeometry.cartesian()` generates a dense TCP path with explicit pitch,
analytical IK and a consistent elbow branch. Knot spacing, joint limits, mesh
floor clearance, protected-object exclusion and midpoint corridor proxies are
checked before dispatch. Approach and return also exclude the target. Joint
velocity/acceleration bounds correspond to `demo_veryslow`. Sampled MoveIt
self-collision validation precedes registration; it is not a proof of continuous
self-collision freedom. Native trajectories provide the independent check of
actual TCP/pitch tracking.
The midpoint screen is an approximation, not a continuous collision proof for
every controller spline. The final source corrects that comment only; its Python
AST is identical to the executed geometry source.

Pure geometry runs in a worker while the main ROS thread continues observations
and cancellation. Read-only planning checks known scene violations; temporary
input unavailability can wait until math completes. Actuator admission and
actual execution additionally require fresh measured joints and an unchanged
gripper frame. Joint samples are selected from a bounded history against exactly
paired native physical time. ROS /clock transport lag does not replace that
physical reference. Pre-robot contact-prefix records are counted; missing later
execution steps still refuse. Source-age limits are not relaxed for CPU load.

`ConstrainedMotion.execute()` hands that trajectory to the existing MoveToPose
owner through its one-use trajectory registration service. It does not create a
second controller owner. The existing internal token prefix causes the server
log to call this backend `attached_point`; here the trajectory comes from the
finger-TCP planner, without an attached object or an MTC planning call.
Declared timeout/unknown-reply paths latch the adapter and forbid further goals,
including cleanup. The CLI stops on every motion exception and owns this helper
for its lifetime. External callers must discard it after any exception; it is
not a durable Runtime owner or a process-wide unknown-state latch. Cancellation
requires the server's strict stop confirmation.

`ContactReceipt` separates the pre-return primitive outcome from physical
contact evidence, return completion, known motion terminal and actual returned
object pose. The JSON schema is `contact-push-receipt/1`; it is also published as
`std_msgs/String` on `/flexcell/contact_push_receipt` with transient-local depth1.
The standalone CLI is the producer. This is not yet a custom ROS action or a
DecisionPolicy/Runtime integration.

## Consuming a returned state

`arm_ready` means the arm can be reconsidered for another action. It requires a
completed return, known terminal, no caller cancellation, fresh quiet joints,
stable measured object snapshots, known gripper, disengaged carry, sufficient
tool clearance and an undisturbed protected object. It does not mean the push or
the complete task succeeded. A successful stroke with a failed return retains
its stroke verdict and emits `arm_ready=false`.

Consumers must call
`ready_for_next(receipt, now_sim_ns, current_world_revision, now_monotonic_ns)`.
It checks source age, revision and the same-host observation time again. The
latched boolean expires; it must not authorize a later motion by itself.
Monotonic timestamps are only comparable on the same host/boot. ROS source stamps
use simulation time. Another process must freshly observe and replan; this
receipt does not reserve the robot or bypass the executor's admission control.
World revision uses a per-observation movement threshold, so an unchanged
revision does not prove an unchanged pose. Re-observe the actual positions and
robot state before planning/dispatch; the standalone driver also checks native
target/gripper changes and the measured trajectory start at that boundary.

`returned_signed_m` is the signed net -x displacement. `return_loss_m` compares
it with the pre-return measurement. `returned_request_geometry_satisfied`
reuses frozen push distance/direction/lateral/vertical limits. Independent
full-task acceptance always comes from the frozen evaluator after execution.

## Running and reviewing

`run_contact_push.py TASK OUT --model MODEL --attempts 2` is an exposed-task
engineering experiment. It reads `expected_goal`; it is not an autonomous Agent
experiment with public inputs only. It uses measured object progress after each
at-most4mm stroke segment and the unchanged `push.judge` conditions.

The acceptance directory contains the preregistration, one-case harness,
real-ROS synthetic protocol checks and a read-only native replay analyzer.
Model files/license, executed source versions, logs, failed experiments and
source hashes belong in the evidence archive. See its README for measured
outcomes and exact replay commands. Do not infer robot capability from unit or
synthetic protocol tests.


## Opt-in public Runtime action and live consumption

The public-only entrypoint runtime/run_public_push_task.py uses live Observe,
a bounded English rule planner and the public object/region registry to build
RunComposite stages. The planner/primitive do not accept expected_goal. This is
engineered execution, not LLM planning or autonomous skill development.

TaskFSM push_backend defaults to legacy. Opt-in finger_tcp uses
contact_push_action=/contact_push, contact_task_motion_budget<=40 and
contact_task_wall_s<=600. ContactPush owns one persistent worker, accepts only
registered -x30mm/demo_veryslow requests and limits each to13 actuator handoffs
and300s. Its readiness service means owner availability, not a physical lease.

Typed results distinguish stroke outcome, known/observed physical contact,
known terminal/stop state, completed return, arm readiness, returned WorldState,
post-return displacement and same-host monotonic observation time. Runtime
correlates actual wire UUID/request and checks frame/source, complete objects,
released carry, known gripper, receipt age<=250ms and object source age<=500ms.
Normal fresh before/after observations and measured stage postconditions remain.
A successful stroke with failed/stale return cannot commit a stage.

Unknown acceptance/terminal, contact transport exceptions or executed aborted/
canceled motion without stop confirmation quarantine the owner and prohibit
another motion/cleanup trajectory. The worker keeps its own node name and
simulation clock; task coordinators use wall clock. Default launches are intact.

At immutable source22f873ba, four real correlated returned states were consumed
in two publicly instructed physical tasks. Both original red and development
blue probe completed two stages and full frozen9/9 acceptance. Receipt ages were
26.5–107.1ms. These are one trial per task in the declared task-scoped graph,
not default-graph repair, formal held-out performance or a promotion decision.
See evobot_runtime_push_20261112/ for raw ZIPs, executed source, failures and
independent replay. Old engineering CLI K-series measurements remain separate.
