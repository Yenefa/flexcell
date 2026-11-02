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

## Preserved startup stop and new declaration

Implementation/declaration `6c3d87b` stopped during preflight with native stream
stale, before any worker or cycle was dispatched. Its complete original files
are in `setup/acceptance/native_five_20261030/startup_6c3d87b.zip`. The strict
500 ms gate was not relaxed. Startup contained 7,062 snapshots per stream:
3.23 MB physics and 24.59 MB contacts. An offline contact JSON parse measured
0.74 s on this host, already greater than the 0.5 s age allowance. Reading all
history before selecting a live frame is a buffering design flaw; exact
in-window parsing latency was not instrumented, so no unique timing claim is made.

The live reader now starts at new complete records for preflight and each new
detached cycle. It discards only its first possibly partial live record to
align the reader; no raw file is truncated or deleted. Every complete cycle's
full raw interval still passes the independent gate before the next begins.
All final raw records, including startup, remain subject to verification. The
new declaration is `infra/native-five-cycle-window-after-live-tail.json`,
linking the preserved startup stop. World/config hashes and all thresholds are
unchanged. This is a distinct declared startup attempt after a reader fix, not
a replacement successful sample. The previous attempt had zero cycles.

The distinct `225a885` window passed preflight but stopped after the first
detached preposition: no engage was requested. The earliest-reference selector
checked freshness before checking eligibility and therefore rejected queued
pre-trigger history (reported age 2,668,183,423 ns). Its complete data and
worker failure are preserved in `preposition_225a885.zip`; this is one started
cycle with zero attachment requests, not a completed cycle.

The selector now checks latest-source freshness, then reference eligibility,
then the freshness of the first eligible reference. It cannot skip a stale
eligible candidate to select a newer passing one. Native producer and candidate
age limits both remain 500 ms. Separate adversarial tests cover pre-trigger
history, a stale eligible candidate and a stale latest source. The new
`infra/native-five-cycle-window-after-epoch-selection.json` links both retained
stops without changing physics, poses, count or acceptance thresholds.

## Complete five-cycle result

Implementation and final declaration commit `858f01a352ca503dd2540102887e33cbd7d089f6`
was verified before dispatch (187 tracked relevant files plus install/import
identity). All three actually mapped first-party observer/guard binaries and
DART/Gazebo libraries matched the recorded installed hashes.

All five cycles completed in the declared A/A/B/B/A order. Actual component
attachment durations were 10.122, 10.120, 10.118, 10.122 and 10.124 sim s.
Reference-to-first-attachment gaps were 10, 6, 6, 6 and 10 sim ms. Maximum
translation errors from each detached preposition reference were respectively
0.5096, 0.156413, 0.2744, 0.1568 and 0.5096 mm (limit 2 mm). The binding
transition is included in those errors. Every cycle passed its independent
full-raw gate before the next started.

Parent translation was exactly unchanged in the retained precision; this is
stationary-arm evidence, not a replacement for moving-arm follow qualification.
All positive controls, physical release/freefall checks, A/B isolation, and
retired-session rejection checks passed. Strict 19-check health passed both
before cleanup and after the final detached reset, IDLE/carry released. Original
joint states, physics, contacts, RPCs and results are retained without filtering.

The complete raw archive and receipt live alongside independently executable
startup-stop, preposition-stop and five-cycle verifiers. Offline/native CI
recomputes each classification; a separate bounded native-five-cycle-smoke job
runs a fresh five-cycle window on PR/main. The previous two stops remain
preserved with zero completed cycles. D3 and the remaining qualifications are
unchanged: moving-arm reference, S2-host picture/fault injection and legacy
backend matrix are still outstanding.

This fixture owns the backend through native RPCs directly, without engaging
the ROS CarryServer adapter. Task/arm motion actions stay idle; ROS/native
ownership consistency is checked only once released. These component cycles
do not qualify the skill adapter or the S2 false-attached intervention.

## Retained consumer-watermark stop

Trusted run 41387963040 at TCP implementation `5196568` passed its joint task,
but the independent native window completed only cycle 0, then stopped after
cycle 1's initial status, before a second preposition or engage. Its cached
joined-frame age was 1,162,552,992 ns. In the retained raw interval after that
status, source-record wall-clock gaps were at most 10.783 ms (physics) and
10.523 ms (contacts). The precise consumer stall was not instrumented; the
29-file original artifact stays STOPPED in `setup/acceptance/native_consumer_stop/`.

The live reader now bounds each stream drain at a captured EOF and releases
the previous cycle's parsed verification data before opening the next live
subscription. A detached/default wait distinguishes raw producer watermarks
from an old joined consumer cache and can catch up within the original timeout.
It never returns a candidate aged 500 ms or more. Either stale producer still
stops the fixture. An eligible stale reference and a stale active-watch cohort
also still stop immediately, even with healthy producer tails. Raw files are
never trimmed, and every full cycle remains independently gated before the next.
Adversarial tests cover all those cases plus a continuously growing input file.

The distinct `infra/native-five-cycle-window-after-source-watermark.json`
links this retained stop. Counts, order, poses, world/config hashes, both
500 ms bounds, the 20 ms binding gap and all physical thresholds stay unchanged.
