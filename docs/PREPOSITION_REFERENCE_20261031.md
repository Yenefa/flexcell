# Pre-attach SE(3) reference: measured before binding, enforced during carry

Status: implemented and unit-tested; the declared CI joint window now runs it.
This closes the "reference is the first observed attachment" gap recorded in
[DETACHABLE_ADMISSION_20261027.md](DETACHABLE_ADMISSION_20261027.md) and
[INTEGRATED_CONTACT_WINDOW_20261030.md](INTEGRATED_CONTACT_WINDOW_20261030.md).
It does **not** change D3: default admission stays **NO_GO**.

## The gap

`JointFollowMonitor` latched its reference from the first *attached* sample. Two
consequences:

1. A pose jump caused by binding itself was invisible: the reference moved with
   the defect.
2. Nothing required the arm to be at rest, or the body to be detached and
   contact-free, when the joint appeared.

So "the box followed the EE" was proven, but "the same constraint holds before,
at and during binding" was not.

## What changed

Runtime (`flexcell_skills/joint_follow.py`, `carry_server.py`):

- `PrepositionLatch` buffers parent/object transforms while the body is still
  detached and hands out the **mean** of a declared at-rest hold. Any attached
  sample clears that body's history.
- `carry_server` requires that hold before the joint is requested
  (`require_preposition_reference`, default true; `preposition_timeout_s` = 1 s)
  and refuses the session with a typed log record
  (`preposition_reference_rejected`) plus a message on the engage reply when it
  is missing.
- `JointFollowMonitor.arm(..., reference, preposition)` anchors the session on
  that reference. The first attached sample is recorded as an **attach jump**
  instead of becoming the reference, and every later sample is measured against
  the pre-attach transform.

Offline (`scripts/preposition_gate.py`, wired as `required_preposition_reference`
in `scripts/sim_window.py`):

- Recovers the true 2 ms attachment interval behind the 50 Hz carry log.
- Requires a 100 ms / 50-step detached hold immediately before attachment with
  no missing step, and requires the target body's own contact sensor to be
  available for every step of that hold — plus the attachment instant — with no
  contact whose counterpart belongs to `open_manipulator_x`. Ground contact is
  expected (the body still carries its own weight) and is reported, not assumed.
- Takes the reference as the mean transform over that hold, requires the hold to
  be at rest, then requires the attach jump and **every** 2 ms attached step to
  stay within the unchanged 2 mm / 1° follow limits of that reference.
- Cross-checks the runtime reference against the raw-log reference (≤ 0.5 mm),
  so the online and offline instruments must agree.

## Declared thresholds (frozen in `infra/joint-contact-attached-center.json`)

| quantity | value | relation to existing gates |
| --- | --- | --- |
| pre-attach hold | 100 ms / 50 steps | immediately before the joint appears |
| hold spread | ≤ 1 mm, ≤ 1.5 mrad | "at rest"; ~1/12 of the 1° follow rotation limit |
| attach jump | ≤ 2 mm, ≤ 1° | unchanged follow limits, no relaxation |
| carry drift vs reference | < 2 mm, < 1° | unchanged follow limits, no relaxation |
| runtime/raw agreement | ≤ 0.5 mm | cross-instrument check |

The gate refuses the window if these constants differ from the code
(`preposition thresholds changed or undeclared`), so a threshold cannot be
tuned after seeing a result.

## Re-analysis of the archived window (not a new run)

`setup/acceptance` already holds a joint window (`feat/integrated-contact-window`,
run 40916246921, artifact `joint-follow-40916246921-1`). Its carry session started
at the sampled instant 28.942 s; the per-step log places the true attachment at
28.938 s and the release at 47.300 s. Re-running the new gate over that raw data:

- pre-attach hold: 50 steps, 28.838–28.936 s, detached throughout, only
  `ground_plane::link::collision` reported as a counterpart
- hold spread: 0.132 mm / 0.477 mrad
- attach jump vs the pre-attach reference: 0.055 mm / 199 µrad
- 9,182 attached 2 ms steps: max 0.0553 mm / 200 µrad from that reference
  (the unchanged limit is 2 mm / 1°)

The maximum drift over the whole carry is therefore the same size as the jump at
binding: the constraint did not change when the joint appeared. This is a
re-derivation from stored raw data, not a new simulation, and it cannot be
presented as a fresh window. It also does not verify the runtime side, because
that run predates the latch.

## Boundaries

- Contact-freedom is claimed only where the target body's own contact sensor
  reported data for every step of the hold. Missing data stays UNKNOWN and stops
  the gate; nothing is filled with zero.
- The runtime latch sees poses only. It can require "detached and at rest"; it
  cannot and does not claim contact-freedom. That claim belongs to the offline
  gate over raw contact data.
- Unsigned/passive force only; signed target-body force is still uncalibrated.
  Contact-grasp physics is still not modelled — this remains a fixed-joint
  simulation oracle.
- One archived window is re-analysed. No success rate, no reliability estimate,
  and no D3 qualification follows. Issues #56–#59 stay open, the model batch
  n ≥ 50 stays frozen, and the next window must be declared and run before this
  gate's own result exists.
