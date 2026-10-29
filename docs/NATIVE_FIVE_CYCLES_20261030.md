# Five native cycles with a detached preposition reference

The baseline is #74, main `4e7800058ca87e264ae7fa0bb5297facee7d4b51`.
Its post-merge offline run 40925517112 and full-stack run 40925517058 passed.
The rejected #73 main window remains rejected and preserved in Git.

This is one new declared window of **five qualification cycles**, in the fixed
order A, A, B, B, A. It dispatches no Pick/Place/MoveToPose task during those
cycles. The real Gazebo robot chain, controllers and native DetachableJoint
backend remain running; controllers hold the canonical reset posture. Parent
motion is measured and reported, but **moving-parent follow is not qualified**.
It is not a contact-grasp, S2-host or real-hardware run. D3 remains NO_GO.

Commit the code and `infra/native-five-cycle-window.json` before execution.
Verify tracked source/install/import identities and actually mapped native
libraries. Run one window, with no replacement cycle or expanded sample count.
Any unexpected reply, missing data, failed per-cycle gate or unknown terminal
stops the worker before the next cycle. Only a completely successful worker
permits the final detached canonical reset. Setup/teardown reset operations
are outside the five qualification cycles and remain recorded separately.

Each cycle explicitly confirms both native attachments absent, waits 1.05 sim s
for the resting positive control, then calls the official world set_pose once
while detached. The fixtures are A=(0.35, 0.18, 0.22) m and
B=(0.35, -0.18, 0.22) m, identity orientation. Separate landing positions avoid
stacking A/B or loading the passive control with two boxes. No set_pose is sent
while attached. The adapter's pin requests only renew the 500 ms lease; the
official fixed joint is the physical attachment mechanism.

The reference is the **earliest complete joined physical/contact frame** after
the set_pose reply with the active body within 5 mm of the declared fixture,
both objects detached and an available empty active contact set. The reference
must precede engage. First attachment must be within 20 sim ms. All raw 2 ms
frames from that detached reference through release, including the binding
transition, must stay below 2 mm / 1 degree relative SE(3) drift. There is no
trim to a convenient first attached frame. Hold for 10.1 sim s, with at least
10 sim s of actual component attachment. Record every physics step, poses,
native RPC and original contact protobuf. Optional per-step file flushing only
reduces observer buffering; it changes neither physics nor publication rate.
Default worlds retain the historical ten-step flush behavior.

The passive box must stay detached and within 2 mm during the active segment.
Its fixed 500-frame pre-reference interval needs at least 476 force samples
and mean vector magnitude 0.392–0.588 N. Contact/motion snapshots must have the
same sim_ns, poses within 1e-12/component and native clock skew at most 50 ms.
All active frames from reference through attachment must be contact-free.
Ground has no sensor and stays UNKNOWN. Empty contact sets are not measured
zero forces. Gazebo's contact-value reuse and uncalibrated signed force limits
from #72/#73 still apply.

Probe other-object engage/pin while active and old-session release/pin while a
new owner is active. After explicit release and 1 sim s settling, an engage
with the retired session and a fresh nearby pose must be rejected while the
native backend is ready and detached. These are declared negative controls.
The first 40 ms after physical joint removal must be detached/contact-free;
all 21 samples must fit gravity -9.8 +/-20%, residual <=0.1 mm. The complete
raw cycle is independently gated **before the next cycle is allowed**. Retain
failures, joint states and force data, not just a pass/fail counter.

The fixture has no camera and does not satisfy the S2 picture/fault-injection
requirement. It does not supply moving-arm preposition-reference evidence or
the legacy x {teleport,joint} matrix. Model n>=50, vision Observe, real hardware
and default backend changes remain frozen.
