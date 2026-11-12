# Configuration-only geometry pilot, before dispatch

The retained audit favors H2: EE advances in the intended direction even when the
object reverses; the five fixed-batch strokes have top-contact fractions about
0.64–1.00. B1's NO_CONTACT result still has 140 native pusher-contact steps.
Contact persists through the recorded stroke ends, so no positive free-flight
tail is observed in those windows. The originally conditional speed pair is
**NOT_RUN**, replaced before execution by this more direct geometry hypothesis.

## Hypothesis and bounded intervention

The existing `contact_height_m` is the virtual EE height. It is not the height
of the finger collision surface. Pinned geometry bounds a distal palm point by
EE-relative [0.0207, 0, -0.029] m. At the measured 29–47 degree pitch its world z
offset is about −35 mm. This is a bounding-box proxy, not a registered physical
TCP or a claim that the extreme x/z corner lies on the mesh. A world EE target
of 55 mm is a falsifiable attempt to bring that distal surface near 20 mm instead
of below the table. Actual contact locations/normals must validate or reject it.

Run one pair, in fixed order G0 then G1, on exposed dev seed2000:

- G0: current feedback/high-hold, world EE height 20 mm, demo_slow.
- G1: identical except world EE height 55 mm.

Maximum three attempts each, 30 mm request / 5 mm overdrive / one increment,
same world/image/solver/success rules and nine-file frozen evaluator. Both use
the same updated CLI; defaults preserve the previous parameters. Endpoints,
continuous contact/physics, post-return states and all failures are retained.
No restart for a favorable physical result. Abort only infrastructure failure.

Primary mechanism: valid bounded primitive strokes under the unchanged existing
±5 mm requested-distance condition, rather than broad task-band success alone.
Secondary: rear-side vs top contact, actual EE/object direction, protected/support/
lift/gripper/attachment gates, complete task verdict, time and attempts.

A positive pilot must show at least one valid bounded stroke AND full independent
task acceptance without physical-evidence violations before earning a separately
preregistered repetition batch. Otherwise reject this configuration as a fix and
retain it as evidence that a static TCP-height correction is insufficient.
A single pair cannot identify a general effect amid randomized motion planning.
No unseen instance, change to release semantics, threshold, core or formal baseline.
