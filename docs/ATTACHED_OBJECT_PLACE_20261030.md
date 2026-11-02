# Joint PLACE plans the attached box center

PR #75's original trusted run 40953343176 passed the new five native cycles and
the full velocity/MTC regression. Its joint task failed honestly after a
successful first PICK: three PLACE trajectories reached their EE goals with
less than 1 mm position error, release was acknowledged, but the box settled
112.617 mm from its target (unchanged 60 mm tolerance). The complete artifact
and executable rejection verifier are in
`setup/acceptance/joint_place_failure_20261030/`.

The native full relative transform remained stable. At first attachment the
box's world offset from the EE was approximately (0, 0, -160) mm. Immediately
before release it was approximately (74, -103, -98) mm after wrist rotation.
The old PLACE calculation still assumed a fixed world-vertical 160 mm offset.
This is a target-frame error, not a failed fixed joint or motion acknowledgement.
The later settled error includes release/toppling dynamics; it is not an exact
measurement of the pre-release offset. GRASP-B-001's historical mechanism is
still UNKNOWN and is not reclassified by this separate PLACE diagnosis.

For MTC + detachable_joint only, hover/descend goals now refer to the attached
box's **shape center**. The private planner uses the measured scene's full
link-to-shape transform with the upstream MTC IK-frame API and the existing
position-only MoveIt constraint adapter. CollisionObject origin and primitive
center can differ; assuming the object's frame name is its center is invalid.
Before planning, the measured shape pose must agree with a fresh independent
Gazebo box pose within the existing carry limits (<2 mm, <1 degree), or planning
stops with carry held. No orientation constraint is added to the four-DOF arm.

After planning-scene detach, MTC MoveRelative plans a world-vertical EE retreat
from the propagated descend endpoint using the same collision-aware planner.
The private service returns FK-derived EE endpoints for all three trajectories.
The adapter maintains the logical box-target ordering but registers and sends
the actual EE targets to the existing single MoveToPose owner. Missing, nonfinite
or wrong-frame endpoint metadata prevents dispatch; object-center coordinates
cannot silently become EE goals. Existing start-state, deadline, cancellation,
stop and unknown-terminal rules still apply. The public Action contracts do
not change. Legacy and teleport/velocity paths retain their existing semantics.

Joint/MTC PLACE independently samples the box again before release and retains
the pose/error in its record. Failure or a miss outside the unchanged place
tolerance holds carry. The final settled ground-truth verification remains
authoritative. This adds no success-rate or high-precision claim.

The new immutable declaration `infra/joint-contact-attached-center.json` links
the rejected original artifact and declares **one** A task, recovery budget 0,
no replacement or extended sample count. World, semantic config, 2 ms physics,
11 s hold, 10 s follow minimum, force/freefall gates and 50 mm release fixture
are unchanged. Commit implementation and declaration before the run; verify
actual imported/installed code and mapped native identities. The old declaration
and failure are retained unchanged. D3 remains NO_GO; S2, moving-parent detached
reference qualification and the legacy matrix remain outstanding.

Contact-profile smoke now records the owned launch tree's actual native mappings
before task dispatch. PhysicsTrace, ContactTrace, DetachableCarryGuard and (for
MTC) the running planner must each match the installed identity, or no task is
sent. DART/Gazebo library hashes are retained alongside them.
