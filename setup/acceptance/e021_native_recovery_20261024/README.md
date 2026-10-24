# E-021 native episode recovery — 2026-10-24

Issue [#31](https://github.com/Yenefa/flexcell/issues/31) recorded that the 60
native episode files referenced by the three E-021 baseline batches could not be
found in the repository or in the laptop episode store, so their complete inputs
and per-decision provenance could not be re-audited. The original execution host
was still reachable. All 60 files were recovered from
`/home/ros/.ros/flexcell/episodes`, every byte was verified, and they are
archived here unchanged.

The batches themselves are **not** duplicated here. `../tau_sweep_desktop_20261005/`
already holds them; the recovery manifest points at those copies and proves they
are byte-identical to both the frozen inventory and the host.

## What is archived

| Item | Count | Bytes | Location |
| --- | --- | --- | --- |
| Native episodes (new) | 60 | 1 870 637 | `episodes/` |
| Baseline batches (already archived, re-verified) | 3 | 243 734 | `../tau_sweep_desktop_20261005/` |
| Manifest with per-file SHA256 and origin mapping | 1 | — | `recovery_manifest.json` |

`recovery_manifest.json` maps every `original` absolute path recorded verbatim in
the batch rows to the basename in `episodes/`. No path inside the batches or in
`../fixed_smoke_window_20261024/historical_inventory.json` was edited. The
recovered reference set is **identical** to the frozen inventory's list — 60 in,
60 out, no additions.

## Verify it yourself

Standard library only. No ROS, no pytest, no network, no model service, no
absolute paths.

```bash
python3 setup/acceptance/e021_native_recovery_20261024/verify_recovery.py
```

```
  batches archived      : 3/3 byte-identical
  episodes verified     : 60/60 sha+size match (60 files on disk)
  reference set         : 60 recovered vs 60 frozen -> identical
  summary batch_20261005_161922.jsonl: {'SUCCEEDED': 18, 'FAILED': 2} dual_object_rows=20 agrees=True
  summary batch_20261005_185833.jsonl: {'SUCCEEDED': 19, 'FAILED': 1} dual_object_rows=20 agrees=True
  summary batch_20261005_192253.jsonl: {'SUCCEEDED': 17, 'FAILED': 3} dual_object_rows=20 agrees=True
  evidence tiers        : byte_recovery=PASS, summary_recompute=PASS, model_source_audit=PASS, model_replay=NOT_RUN, physical_acceptance=NOT_RUN
  provenance tally      : 315 routed of 478 steps, 275 fast proposals (275 with weight digest), 31 paid
  initial_world_state   : 0/60 episodes record it

VERDICT: VERIFIED
```

Exit 0 means every digest, size, batch summary and reference-set claim holds.
Exit 1 means something drifted. Exit 2 is an input error.

A verifier that always prints VERIFIED proves nothing, so it ships with its own
adversarial test:

```bash
python3 setup/acceptance/e021_native_recovery_20261024/selftest_verify_recovery.py
```

```
  A clean archive verifies         PASS  (exit=0)
  B one flipped byte rejected      PASS  (exit=1)
  C deleted episode rejected       PASS  (exit=1)
  D unlisted episode rejected      PASS  (exit=1)
  E tampered batch rejected        PASS  (exit=1)
  F reference set shrink detected  PASS  (exit=1)

6/6 cases behave as specified
```

Both scripts were run on Windows (CPython 3.13) and on the execution host
(Ubuntu 24.04, CPython 3.12) with `PYTHONPATH` cleared, and CI runs them on every
push.

## Per-decision provenance, recomputed

E-021 asserted that every model decision passed the routing provenance audit and
that this rested on the runner's own summary JSONL. Each recovered hybrid episode
carries a per-decision `policy_trace`, so the assertion is now recomputed from the
native records instead of trusted:

```bash
python3 setup/acceptance/e021_native_recovery_20261024/decision_audit.py
```

| arm | decisions | fast proposals | paid proposals | gate failures | fast weight identity |
| --- | --- | --- | --- | --- | --- |
| `batch_20261005_161922` (τ=0.03) | 156: fsm 20 / fast 131 / paid 5 | 136 | 5 | 0 | `clef-flash-q8_0` @ `8754b06f…` |
| `batch_20261005_185833` (FSM control) | 163, pure FSM | — | — | — | no routing, by design |
| `batch_20261005_192253` (τ=0.85) | 159: fsm 20 / fast 113 / paid 26 | 139 | 26 | 0 | `clef-flash-q8_0` @ `8754b06f…` |

Findings that matter:

- **The 139 reproduces exactly.** E-021's "139 decisions in the τ=0.85 baseline,
  zero reported violations" now corresponds to 139 fast-arm proposals with a
  single weight digest and **0** gate failures in the native records. The summary
  number and the native records agree; the claim is no longer self-attested.
- **One weight identity per arm.** All 275 fast proposals across both hybrid arms
  resolve to `clef-flash-q8_0`, digest `8754b06f7d16d6d6ab63493b2ee385cc0ed6abde8c25c39298dc3e1eb05593d9`,
  one calibration digest `0af588a8…`. No arm mixes identities.
- **Escalations reconcile.** τ=0.85: 26 paid decisions = 21
  `fast_unavailable_or_below_threshold` + 5 `uncalibrated_fast_confidence`.
  τ=0.03: 5 paid decisions = 5 `uncalibrated_fast_confidence`. Nothing is
  unaccounted for.
- **Paid spend is bounded, not measured.** Every paid proposal carries
  `USAGE_SETTLED_AT_PEAK_UNCACHED_CEILING`, i.e. an upper bound. This is why
  E-021 quotes ¥5 rather than a metered figure.
- **Small correction to E-021's prose.** The τ=0.03 arm's paid slow fraction is
  5/156 = **3.2%**, not "~0%"; τ=0.85 is 26/159 = **16.4%**, slightly under the
  quoted "~20%". The direction of both claims holds, the magnitudes are now exact.

`decision_audit.json` records the full breakdown. Exit 1 on any contradiction: a
pure-FSM arm that suddenly contains routed decisions, a routed step with no
trace, two weight digests in one arm, a failed gate, or a fast proposal without a
digest.

## Evidence tiers — what is and is not established

| Tier | Status | Basis |
| --- | --- | --- |
| Byte recovery | **PASS** | 60/60 SHA256 + size, reference set identical to frozen inventory |
| Summary recompute | **PASS** | 18/2, 19/1, 17/3 and 20/20 dual-object rows recomputed from archived bytes |
| Model source audit | **PASS for fast arm, bounded for paid arm** | 275 fast proposals carry model name, weight digest, calibration digest, token count, gate outcome; paid proposals stop at call id + cost settlement because remote backends publish no weights |
| Model replay | **NOT_RUN** | no `initial_world_state` in any of the 60 episodes; recorded `policy_input`/`policy_output` pairs support offline decision replay, not end-to-end model replay |
| Physical acceptance | **NOT_RUN** | no robot or simulator was started; magnetic-carry simulation backend, see ADR-001 |

**This recovery does not qualify history.** It restores portability and
auditability of already-recorded evidence. It does not create a fixed
five-attempt smoke window, does not upgrade any n=20 result into a benchmark, and
does not touch the frozen `../fixed_smoke_window_20261024/` archive. All 60
episodes come from a single scenario (`week1_demo_v1`), a single seed (`0`) and
three runtime fingerprints — one per arm. `n≥50` remains frozen, M3 remains
NOT RUN, and the six baseline failures remain the same grasp-physics family
described in E-021.
