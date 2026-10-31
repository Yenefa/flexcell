# Pre-attach stationarity in world coordinates

The owner delegated selection and completion of high-value work on 2026-10-31.
This repair addresses the two outstanding geometric review findings on #77,
stacked on #80 at 3e1f986. No default-backend or D3 admission change is in scope.

The documented pre-attach contract requires a detached, stationary arm and box.
Relative-transform spread alone cannot prove this: a common rigid world motion
leaves that transform unchanged. Both the runtime latch and raw-log gate must
also bound parent and object world-pose spread by the existing 1 mm / 1.5 mrad
limits. Continue to use the relative pose as the carry reference, since absolute
stationarity is required before binding, not during the subsequent movement.

Equivalent quaternion signs must not change the reference or its acceptance.
Normalize validated samples, align quaternion hemispheres, average, normalize;
do not change the existing angle/spread thresholds. Retain invalid/nonfinite
quaternion rejection and explicit UNKNOWN contact observations.

Record parent/body world spreads separately from relative spread in new runtime
and offline evidence. Historical raw windows can be replayed under the corrected
geometry, but missing runtime world-spread metadata stays explicitly unrecorded;
replay does not retroactively exercise the new latch. Old artifacts are immutable.

Acceptance: runtime and offline counterexamples for common world translation and
rotation must fail, stationary antipodal quaternion samples must pass, existing
geometry/contact/stop tests remain valid, and one predeclared local Joint window
must execute and pass its unchanged physical gates. Preserve a stopped window
without replacement if any gate fails. Publish the fix as a new stacked PR.

Alternatives: keeping a relative-only hold fails the stationary requirement;
adding a new controller or velocity estimator changes more than needed. Pose
spread in all three frames directly tests the existing documented contract.
