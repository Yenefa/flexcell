# Signed contact force: one known direction is now calibrated

Status: implemented, unit-tested, and executed once on the local stack. This closes
the "signed target-body force is not calibrated" line in
[DETACHABLE_ADMISSION_20261027.md](DETACHABLE_ADMISSION_20261027.md) **for one
known direction only**. D3 stays **NO_GO**.

## What was missing

`contact_gate.observation` summed the raw `body_1` contact forces and compared the
**magnitude** against m·g. A magnitude cannot tell a support force from a suction
force, cannot tell a vertical load from a lateral one, and cannot notice that a
single contact point is pulling the body the wrong way. Every sentence about
"signed target-body force" therefore stayed unproven.

The pipeline already carried the information: each `Contact` entry names
`collision1` (the watched body's own collision) and `collision2` (the partner), and
each wrench point carries `body_1_wrench` / `body_2_wrench`, i.e. the forces applied
**to** each body. `body_1` is the watched body, so `body_1_wrench` is the force the
partner applies to it.

## What is checked now

`scripts/signed_force_gate.py`, wired into `contact_probe.py` and frozen against
`infra/contact-probe.json`:

- every settled sample must have a complete contact force (missing data stops it);
- the partner must be the declared one (`ground_plane`), so the sign cannot be an
  accident of collision ordering;
- every contact point's `body_1` z component must be **positive**: each point
  pushes the body away from the ground;
- the summed force must lie along the declared `(0, 0, 1)` within
  `max_cosine_error = 1e-3`;
- the summed z magnitude must stay inside the already-declared m·g band
  (0.392–0.588 N), and the lateral component must stay under 1e-6 N.

The gate refuses a window whose declared block differs from these values.

## Result (`setup/acceptance/signed_force_20261031/`)

One declared probe run, 501 settled samples at 2 ms:

| quantity | value |
| --- | --- |
| summed force on the target, z | 0.48999999999 … 0.49000000035 N (= m·g, m = 50 g) |
| direction cosine vs +z | 1.0 |
| maximum lateral component | 3.6e-16 N (limit 1e-6 N) |
| contact points acting downward | 0 of 4 per sample |
| contact partner | `ground_plane::link::col` only |

The receipt keeps the 501 settled rows the gate consumes plus the raw file's
SHA-256, so the check can be replayed from the repository.

## Boundaries

- **One known direction.** Gravity loading is signed and calibrated; a known
  lateral, oblique or tensile load is not, and torque is not.
- The fixture is a resting box: no arm, no attachment, no grasp. Collisions without
  a contact sensor remain UNKNOWN and are never filled with zero.
- No success rate, no MTBF, and no D3 change: default admission stays **NO_GO**.
