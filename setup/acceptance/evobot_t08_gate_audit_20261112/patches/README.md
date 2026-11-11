# Patch set: verify.py v1.1.0 + evaluate.py v0.6.0

**Status** PROPOSED. Not applied. `verify.py` v1.0.0 is left byte-identical.

These are not `git apply` diffs for the verifier — v1.1.0 is a **new file** (the
project's own discipline: a changed acceptance protocol becomes a new version, as
`evaluate_v0.3.0.FROZEN.py` was preserved).

| file | what it is |
| --- | --- |
| `verify_v1.1.0.py` | the proposed verifier v1.1.0 (importable copy: `verify_v1_1_0.py`) |
| `evaluate_v0.6.0.diff` | the proposed evaluate.py change, as a unified diff |

## What v1.1.0 changes, and the finding each change closes

| change | closes | how it is proven |
| --- | --- | --- |
| `verify()` accepts `spec`/`spec_path`; `rest_height_m` is recomputed from `spec.objects[].initial_pose[2]`; a disagreeing declared value is a hard fail | **F1, F2** | `reproducers/verify_v110_closes_bypass.py` — the F1 carry passes v1.0.0, rejected by v1.1.0 |
| new `integrity` gate: `bundle_sha256` recomputed, `manifest.files` non-empty, `task_sha256` compared to the spec file | **F4, F5** | same reproducer, 'edited bundle, stale digest' |
| new `run_binding` gate: `run_id` must equal the run being graded; every sample must lie inside `execution_window` | **F6, F7** | same reproducer, 'replayed bundle, wrong run_id' |
| new `completeness` gate: non-zero `dropped_samples` fails | **F12** | `repro_9gate_audit.py F12` |
| `pusher_contact` requires `pusher_links` ⊆ `allowed_pusher_links` | **F9** | same reproducer, 'floor as pusher' |
| `gripper` refuses a span of fewer than 2 samples | **F8** | same reproducer, 'one-sample gripper span' |
| `no_attachment` requires `events == 0` when `attached_during_window is False` | **F15** | `repro_9gate_audit.py F15` |
| field renamed `max_aperture_change_rad` → `max_aperture_change_m`, reported as `limit_m` | **F18 (naming only)** | — |

**The aperture limit VALUE (0.002) is deliberately unchanged.** See
`FINDING_F18_GRIPPER_CORRECTION.md` §4 — changing it would be a threshold change made
after seeing a trial fail, which the mission forbids.

## Verification

```
python3 setup/acceptance/evobot_t08_gate_audit_20261112/reproducers/verify_v110_closes_bypass.py
  -> 7 checks, 7 as expected, 0 UNEXPECTED
```

v1.1.0 rejects the F1 bypass, keeps the honest push, and refuses replay, stale digest,
floor-as-pusher and one-sample gripper. Run against the real batch it agrees with
v1.0.0 on **10/10** trials (0 divergence) — it adds strictness without changing any
verdict this round.

## Gate count note

v1.1.0 reports **12** gates, not 9: the original nine plus `integrity`, `run_binding`
and `completeness`. The nine are unchanged in name and order so a diff stays readable.
Mission §10.5's conjunction is a subset of this; adding gates cannot turn a fail into a
pass.
