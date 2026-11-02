# Position-only planning at the measured object center

The rejected `c2583ae` window had one successful first PICK, then no valid
PLACE-hover goal. No PLACE trajectory or intentional release was dispatched.
Its complete 36-file archive and executable rejection check are retained in
`setup/acceptance/attached_center_stop/`. The former 112.617 mm settled miss
remains a separate retained failure. Neither is reclassified as a success.

The upstream Jazzy IK sampler subtracts a randomly sampled orientation times a
link's target-point offset before calling KDL. Position-only KDL ignores that
orientation. The resulting EE position can be valid while the offset point
misses its own position constraint. Increasing attempts or tolerances does not
correct the frame semantics.

`scripts/offline_tcp_probe.py` uses the stopped window's recorded stationary
joint state and physical link-to-object transform. Original-scene CDR was not
captured in that old window: this reproduces the same target and offset issue,
not every historical collision-scene detail. On the installed MoveIt 2.12.4,
original offset constraints yielded 0/20 valid samples; the tool-tip model
yielded 20/20 within the unchanged 0.1 mm planning tolerance. A blocking sphere
yielded zero accepted samples with collision callbacks observed. All three
offline hover/descend/retreat plans passed. These are software probes, not robot
task samples or grasp success-rate estimates. Seeds and full logs are retained.

The adapter adds one fixed, geometry-free TCP link to a planning-only copy of
the URDF, at the measured attached shape center. An additional SRDF arm group
uses the same four actuated joints and the existing upstream position-only KDL
plugin with that real tool tip. MTC hover and descend constrain this link's
origin with zero artificial point offset. The original arm group and EE tip
still handle retreat after detach. The original robot description, physical
robot, controllers and actuator joint names remain unchanged.

The original scene's measured attachment must still agree with the independent
physical pose (<2 mm, <1 degree). All collision checks, planning tolerances,
scene propagation and trajectory execution ownership remain in their existing
components. FK-derived EE endpoints are returned to the sole MoveToPose owner;
public Action contracts are unchanged. Adapter/model construction failure
returns a planning failure before execution, without releasing the carry.

For subsequent MTC smoke windows, `mtc_plans/` retains original request, scene,
and initialized parameters as ROS CDR, plus the exact planning URDF/SRDF before
planning. Evidence-write failure blocks the plan. This permits faithful later
offline reconstruction instead of inferring a lost scene from motion logs.
Successful planning responses retain trajectories and actual EE endpoints too.
The complete offline probe, wire records, source snapshots and receipt are in
`setup/acceptance/virtual_tcp_offline/`; its read-only verifier launches no solver.

The native test suite runs the offline sampler/collision/three-stage probe.
The new immutable `infra/joint-contact-virtual-tcp.json` declares one A task,
recovery budget zero, no replacements, and links both preceding stops. World
and semantic-config hashes, 2 ms physics, 11 s hold, existing contact/freefall
limits, and the 50 mm release fixture remain unchanged. Implementation and
declaration must be committed before dispatch; verify imported source and the
actual mapped planner/plugins.

Implementation/declaration `5196568` subsequently completed its single local
task first attempt: PICK, PLACE and VERIFY all succeeded without recovery.
Pre-release physical error was 0.711 mm; final independent VERIFY error was
5.126 mm (unchanged 60 mm zone tolerance, not a precision qualification).
The carry interval was 16.9 sim s, with 8,451 complete 2 ms frames and 9,212
same-round contact/pose joins. The 500-sample passive load mean was 0.49 N;
the 40 ms freefall fit gave -9.8 m/s². Strict 19-check health passed, IDLE/carry
released, and recorder/owned launch exited cleanly. The complete 53-file raw
window, exact planning inputs/model/responses and independent replay/wire
handoff verifier are in `setup/acceptance/virtual_tcp_runtime/`. This is one
bounded task, not a success-rate estimate; the older stops remain rejected.

D3 remains NO_GO. This does not qualify S2 intervention, moving-parent follow
against a detached reference, the legacy backend matrix or real hardware.
