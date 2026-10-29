# Same-round joint/contact/release integration

This declaration extends the standalone contact observer in #72 into the arm
runtime. It does not change a production backend or admit D3. The local manifest
is `infra/joint-contact-window.json`; the camera-free PR CI manifest is
`infra/joint-contact-ci-smoke.json`. Each contains exactly one logical task,
target A, MTC planning and explicitly selected experimental DetachableJoint.
Commit the implementation and manifests before dispatch. No replacement task,
retry to fill the window, threshold adjustment or retrospective qualification.

The generated world adds official contact sensors to both existing box
collisions, a read-only ContactTrace observer, and collision entity names.
Physics remains fixed at 2 ms. No new collision geometry, force controller or
attachment mechanism is added. The ground collision has no contact sensor and
must remain UNKNOWN. Empty available contact sets remain NO_REPORTED_CONTACTS;
neither is a measured zero force.

The **qualification-only release clearance is 50 mm**, compared with the
unchanged 12 mm production default. This deliberately provides a short ballistic
interval and is included in the declared configuration hash. It is not a changed
success tolerance and does not satisfy legacy-backend parity. Joint follow holds
for 11 simulation seconds, with at least 10 seconds required by the existing
independent 2 mm / 1 degree SE(3) gate.

The new offline gate requires complete 2 ms contact/motion joins from one second
before attachment until 0.5 seconds after physical joint removal. Both plugins'
body poses must agree within 1e-12 m/component and their native monotonic clocks
within 50 ms. Collision bindings must remain distinct and stable. All raw
contact snapshots are parsed for nonfinite data, including outside that join.
Reported box contacts require complete bilateral force vectors. The passive
box's fixed 500-frame prebinding interval requires at least 476 measured force
samples and mean vector magnitude 0.392–0.588 N (50 g times 9.8, +/-20%).

The first 40 ms after the physical joint component disappears is fixed in
advance: all 21 samples must be detached and report no contacts. Fit a quadratic
to object z, requiring acceleration -11.76 to -7.84 m/s^2 and maximum residual
0.1 mm. Initial vertical velocity is fitted, not assumed zero. Contact during
that interval, missing force data or incomplete frames stops the window.
Camera images and joint states are recorded by the existing recorder; the
camera is not the source of the 500 Hz force or release measurement.

Limitations: Gazebo may reuse contact values within its 1e-6 comparison tolerance;
sampling every physics step does not prove an independently refreshed solver
force every step. Signed target-body force is not calibrated. This remains a
fixed-joint simulation oracle, not contact grasp. Contact validation is offline;
the existing online follow guard remains responsible for motion safety. The
reference is the first attached pose, not an explicit detached set_pose
reference. Five lifecycle cycles, formal preposition reference, S2-host image
and false-attached fault injection, and legacy parity remain outstanding.
Issues #56–#59 remain open and D3 remains NO_GO.
