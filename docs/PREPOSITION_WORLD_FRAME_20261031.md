# Pre-attach stationarity: world frames and equivalent quaternions

The existing at-rest contract in #77 checked only relative parent/body poses.
A common rigid world motion preserves that transform, so both online and offline
checks could admit a moving hold. The arithmetic quaternion mean also rejected
equivalent stationary q/-q representations. These are the two review findings at
[world motion](https://github.com/Yenefa/flexcell/pull/77#discussion_r4427502551) and
[quaternion signs](https://github.com/Yenefa/flexcell/pull/77#discussion_r4427502558).

## Repair

`PrepositionLatch` retains validated parent and body world poses alongside each
relative transform. Both world spreads and the relative spread must meet the
existing **1 mm / 1.5 mrad** hold bounds. The reference used during the subsequent
carry remains relative SE(3), so ordinary arm motion after binding is allowed.
Quaternion means align the samples to the same hemisphere before averaging and
normalization; the normalization/spread rejection bounds are unchanged.

`preposition_gate.py` independently derives the world-pose spreads from every
2 ms raw hold step, retains the target contact-sensor checks and enforces the
same reference over the whole attachment interval. New runtime records contain
`world_at_rest` measurements. Historical missing metadata is **UNRECORDED**,
not measured zero; replaying old raw data does not retrospectively run the new latch.

## Tests and review

The six new geometry cases failed on the old implementation: online/offline
common translation, common rotation and stationary antipodal quaternions.
They pass after the repair. Four additional metadata cases reject missing scalar
fields, NaN, negative and over-limit values. The complete isolated build/test
reported **708 tests, 0 errors, 0 failures, 0 skipped**, and the 40-file static
scan reported zero problems. A read-only review found no actionable defects.

## One new local window

Implementation/declaration `19caa0199660c6a0d9d95af14620695dde0eedcf` was frozen before the
run. The new `infra/joint-preposition-world.json` declares one A task with no
recovery or replacements. The world, semantic configuration, 2 ms step, follow,
contact, release and hold bounds remain unchanged. Git object archives of all
four locked upstream revisions were built in isolated ext4 prefixes; the old
dirty WSL checkout was retained, and its saved patch remained unchanged.

Window `56693027e5444c3ca559acd3a4f6b1ad` / `run-038b65f1b506` passed its first task:
PICK, PLACE and VERIFY all succeeded. Raw final placement error was
**5.146469 mm**; the latest physical frame was
8.597 ms old at task return. Post-task reset and
all 19 strict health checks passed; recorder/stack
cleanup completed with zero residual runtime processes.

| measurement | runtime: 5 samples / 80 ms | raw: 50 steps / 100 ms | bound |
|---|---|---|---|
| parent world translation | 0.045727 mm | 0.057469 mm | 1 mm |
| parent world rotation | 0.562690 mrad | 0.707184 mrad | 1.5 mrad |
| body world translation | 0.000000 mm | 0.000000 mm | 1 mm |
| body world rotation | 0.000000 mrad | 0.000000 mrad | 1.5 mrad |

The pre-attach target contact sensor reported only the ground as counterpart.
Runtime/raw reference position agreement was
2.339362 micrometres. The complete raw attachment
interval had 8,665 steps; its maximum relative translation
from the pre-attach reference was 0.081796 mm.
The sampled follow interval spanned 17.30
sim s. All 28,197 raw physics steps are continuous. The joined
contact/motion gate passed 9,411 steps; its fixed
40 ms release fit measured -9.800000
m/s² over 21 samples. Actual PICK/PLACE CDR snapshots and their models were retained
and decoded by the planner snapshot gate.

## Replay and limits

The complete **60-member**, **4,566,165-byte**
raw ZIP is committed in `setup/acceptance/preposition_world_20261031/`.
Each member was byte-verified against its source before publication. SHA-256:
`014fd1e4d25e4fd2858d2e9440cfbfcc9cd3257ee5949a1ae72d4f1229111727`.

Replay without ROS services or actions:

```bash
python3 setup/acceptance/preposition_world_20261031/verify.py
```

With the ROS message packages sourced, add `--planner` to decode and check the CDR
snapshots as well. The verifier checks ZIP/member hashes, the actual imported and
mapped native identities, positive task semantics, raw preposition/follow/contact
gates, physical final position and post-run health.

One bounded success is not a reliability estimate. D3 remains **NO_GO**; no default
switch or model-batch unfreezing occurred. The separate signed-force probe is only
a known gravity direction. The MTC/carry comparison in #80 does not satisfy the
literal `skill_backend=legacy` matrix required by #59. Historical native-five-cycle
stream-staleness failures also remain a separate unresolved item; none is replaced
by this window.
