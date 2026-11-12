# Finger TCP, constrained trajectory and returned-state interface

Base 6186271b. Isolated development only. Nine frozen files, core PushObject,
TaskSpecs, existing success thresholds and ordinary launches stay unchanged.
No hardware, paid model, PR/main merge or baseline promotion.

## Before motion: measured-model hypothesis

Extract the exact simulation URDF/STLs and preserve their hashes/license. At the
current uncommanded gripper state, distal inner faces are approximately 42 mm
apart while the task box is 35 mm wide. A centered EE point can pass between the
fingers. Use one actual left-finger surface, lateral arm offset and fixed pitch;
do not command the gripper or assume its bounding-box corner is a contact TCP.

Select the largest real distal bottom triangle whose transformed normal meets
the declared rear-side condition. Register its actual clipped support point,
including plane/triangle identity and mesh hashes. Use 85 degree pitch: the
offline geometry scan found 89/90 degrees unreachable, while 85 retains joint
margin and a largely horizontal rear-facing surface. Nominal initial rear gap
1.5 mm; whole moving-mesh floor clearance at least 1 mm, nominal tool floor
reserve 2 mm. These are extra candidate guards, not changed task acceptance.

Plan exact TCP/orientation paths using the validated four-joint model, not
position-only goal sampling. Guard every path knot and cubic midpoint for floor/
protected geometry; guard target exclusion during approach/return. Check sampled
MoveIt self-collision states before one-use handoff to the existing MoveToPose
executor. That executor retains admission, execution, cancellation and unknown
terminal handling. No second direct controller owner is introduced.

Nominal object request remains 30 mm. Advance in at most 4 mm constrained TCP
segments, stop from measured object progress, at most requested+5 mm TCP travel,
maximum nine stroke segments. Native contact must be on the selected finger,
rear-side/horizontal-normal fractions >=0.7, sampled contact-to-real-patch error
<=2 mm. Wrong surface/source/unknown motion stops further dispatch. No contact
progress after two segments rejects the attempt. Use the unchanged frozen
`push.judge` distance/direction/lateral/vertical conditions, plus native contact.

Unload 3 mm without changing pitch, then lift/rotate along a checked exclusion
path. A returned receipt separately exposes primitive outcome, actual net pose,
return completion, known motion terminal and arm readiness. Readiness requires
fresh quiet joints, stable object snapshots separated by >=0.1 simulation second,
carry disengaged, known gripper, tool floor clearance >=55 mm and protected
excursion <=5 mm. Latched readiness expires with time/revision; consumers must
re-check it. Unknown terminal allows no cleanup goal. A failed return never
rewrites a good pre-return stroke or claims the next action is safe.

## Minimum physical experiment and decision

First one candidate pilot on exposed seed2000, maximum TWO nominal requests and
40 actuator goals, one simulator. Keep all native 5 ms/contact/joint/state/plan/
receipt data. Instantiate scene before launch with the new adapter and verify
initial xyz/yaw. No live state editing. Use the frozen independent grader only
after execution, outside the controller.

Mechanism gate: at least one requested stroke passes the unchanged bounded
conditions, actual contact matches the registered patch, AND a valid returned
receipt has arm_ready=true and returned_request_geometry_satisfied=true. Full
task acceptance is reported separately. Only a passed mechanism earns a fixed
control/candidate comparison and separately preregistered repeats. The control
uses the prior feedback/high-hold method, same task/world/profile/attempt cap and
executor deadlines. Do not pool this pilot or earlier batches into that comparison.

Retain failures. First diagnose recorded phase/contact/terminal evidence before
changing the candidate; preserve executed source versions and preregister a new
hypothesis for any retry. No identical favorable rerun. A failed model/contact
guard is a real rejection, not evidence missingness to be discarded.
