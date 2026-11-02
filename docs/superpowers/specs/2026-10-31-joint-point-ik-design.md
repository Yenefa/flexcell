# Joint PLACE attached-point planning

Scope follows the owner's instruction to continue the TCP adapter repair and
validate it in the local simulator. Preserve the four-DOF, position-only Action
contract, sole MoveToPose executor, collision checking, tolerances, deadlines,
cancellation and historical rejected evidence.

The local c2583ae window reproduced the PLACE hover failure after a successful
PICK. The upstream sampler/KDL diagnostic independently demonstrated that a
nonzero point offset can fail even at a known-reachable point.

Three approaches were considered. Repeated EE-position compensation would add
a custom numerical loop and risk freezing an unchecked IK branch, repeating
the pre-#74 weakness. Adding orientation constraints would change the four-DOF
contract. The selected approach represents the measured attached point as an
actual fixed tip in a planning-only model and uses upstream KDL/OMPL/MTC.

Build a private model from the existing URDF/SRDF plus one collision-free fixed
point link and a four-active-joint alias of the arm group. Copy the existing
kinematics and joint-limit configuration into a private, namespaced loader.
The robot/Gazebo description and controllers are never replaced. Preserve the
original arm group for the world-vertical EE retreat after planning-scene
detach. Original links, collisions, attached-body transforms and FK-derived EE
executor endpoints remain authoritative.

Hover/descend use the point-tip group with zero point offset, avoiding the
sampled-orientation/position-only mismatch. Do not precompute one unchecked
joint goal. The old position-only path remains unchanged for PICK, legacy and
velocity use. Retain the private loader through task destruction.

Before a new committed simulation declaration, require a regression that drives
the actual planning service with a frozen measured scene, proves the current
implementation fails, then requires successful plans and independent FK of
the returned point/EE endpoints. Capture exact requests, scene replies and
responses for future replay. Run package regressions, the unchanged five-case
baseline and one declared Joint task. Stop and preserve any failed window.
D3 remains NO_GO regardless of this one task's outcome.
