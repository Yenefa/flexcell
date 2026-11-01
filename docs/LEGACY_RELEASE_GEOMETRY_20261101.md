# Legacy/joint release geometry: one stopped local diagnostic

One source-frozen local task completed at **35.553473 mm** error under the unchanged
60 mm tolerance. The outer window is **STOPPED**: the existing preposition gate
rejected its release-boundary coverage. A further raw replay rejects the 100 ms
pre-attach stationarity interval too. Neither rejection is waived. The production
skill, carry, motion, default backend and thresholds are unchanged; D3 is **NO_GO**.

## What the raw record establishes

Legacy PLACE targets the EE at the requested box position plus 12 mm clearance and
a fixed world-vertical 160 mm offset. A native fixed joint instead preserves a
link-relative transform. This diagnostic measures that mismatch on the actual
released session, rather than inferring it from cross-window maximum errors.

The original bag's `/tf_static` message gives `link5 -> end_effector_link =
[0.126, 0, 0, 0, 0, 0, 1]`. Its raw CDR is decoded both with ROS and an independent
stdlib reader; all fields match. The simultaneous 2 ms physics poses at the last
attached step provide the EE and box release positions. The immediately preceding
detached step supplies the measured parent/box reference. It is explicitly a
**diagnostic reference**, not a stationary/qualified hold or an attached-frame fit.

For this record, the predicted box position agrees with the observed release
position to **0.039415 micrometres**. This describes numerical rigid-transform
consistency in this simulation; it is not physical-world accuracy.

| Vector component | x (mm) | y (mm) | z (mm) | horizontal norm (mm) |
| --- | ---: | ---: | ---: | ---: |
| EE tracking at release | 2.197367 | -2.912987 | 5.847231 | 3.648824 |
| rigid offset versus assumed vertical offset | 15.286426 | -25.421095 | -1.579442 | 29.663225 |
| rigid prediction residual | 0.000003 | -0.000005 | -0.000039 | 0.000006 |
| movement from last attached step to final observation | 1.309021 | -1.846693 | -16.267794 | 2.263584 |
| declared release clearance | 0 | 0 | 12 | 0 |
| final error relative to requested box goal | 18.792818 | -30.180779 | -0.000044 | 35.553473 |

The vectors sum to the final error, with 1.77e-17 m closure residual. Their norms
must **not** be added or interpreted as causal percentages. Before release, the
box already had **33.294197 mm** horizontal error. Falling/settling therefore
cannot account for all of this window's lateral error. The terminal motion log
reports 7.850902 mm EE error; the later simultaneous release step measures
6.892317 mm, so those two observations are reported separately.

Changing the target would change the future trajectory, orientation and contacts;
this accounting is not a measured counterfactual improvement. The original #86
45.007 mm event has no equivalent sealed release decomposition here and its exact
mechanism remains **UNKNOWN**. Its maxima do not establish that skill dominates
carry as a causal population effect.

## Both rejected qualification boundaries remain rejected

The run has 27,608 continuous 2 ms physics records and 27,608 matching contact
ticks. Within the declared task there is exactly one native attachment:

- Last detached reference: 26.606 sim s; first attached step: 26.608 sim s.
- Last attached step: 34.026 sim s; first detached step: 34.028 sim s.
- The sampled follow summary ends at 34.002 sim s: a **24 ms** attached tail,
  beyond the existing gate's **20 ms** bound. Replay reproduces the exact refusal.
- The full 50-step/100 ms raw pre-attach hold has **0.497918 mm / 1.640896 mrad**
  spread, exceeding the unchanged **1.5 mrad** angular limit. The online five
  samples/80 ms had measured 0.380092 mm / 1.252598 mrad. The different temporal
  coverage matters; the offline rejection is not converted into a pass.

Source investigation shows `begin_release()` disables `feed()` before the carry
worker is joined and before native release acknowledgement. This explains why an
intentional-release interval can exceed the sampled monitor's recorded tail. The
original run lacks a dedicated monotonic request/reply receipt for that release,
so the precise internal timing split remains **UNKNOWN**. The geometry analysis
uses complete raw steps without changing the monitor or the old verdict.

## Source, execution and validation

Runtime/declaration commit: `66cff2e650c7489aa59f8cce4ab8685dad59ae6e`, based on #85.
Window `8e2481ef4ed04aeaa2d9519407068c59`, run `run-3edeaffca614`.
One A task, zero recovery/replacements; runtime wrapper exit **1**, wall **86 s**.
The added 2 ms trace/contact instrumentation and no-recovery setting distinguish
it from #86's functional matrix. It does not fulfill #59's CI requirement.

The isolated Git LF source archive is 1,341,440 bytes, SHA-256
`b6cfe03b81f5d3e54c92ceaa74f98f1d066468f68a8f777355c7123870a15957`.
Imported first-party Python/launch bytes match it; mapped native library SHA values
match the qualified install. Native source/build inputs, including the Gazebo
`.cc` files, match the previously qualified source. Before/after runtime identities
match. Post-task reset/health pass, recorder/launch exit 0, no runtime processes
remain, and the old dirty WSL patch SHA is unchanged. No old checkout was restored.

The complete original experiment is `setup/acceptance/legacy_release_20261101/raw-window.zip`:
**69 members, 4,847,937 bytes**, SHA-256
`3eba98d3d3bb184bdf517130690a21e7b9cfaec69a6b75719ec50eaae0dfc903`.
It includes full raw steps, contacts, rosbag, source tar, logs, identities, health,
reset, postflight, declaration and capture tools. Each member was byte-compared
against its stable source after shutdown. Original raw evidence is never edited.

The 24 new offline tests cover rotated geometry, vector cancellation, invalid
inputs, ambiguous task sessions, missing/reordered steps and real/corrupt CDR.
The complete Python suite passes **766 tests** with the same three existing fork
warnings; the static scan reports **40 files, zero problems**. Production C++ is
unchanged and no new native build or C++ validation is claimed.

Replay with Python 3.12+, without ROS, services, a controller or site packages:

```bash
python -I -S -B setup/acceptance/legacy_release_20261101/verify.py
```

Exit 0 means **DIAGNOSTIC_REPLAY_COMPLETE**, with the original **STOPPED** window,
both rejected boundaries and **NO_GO** still present. It is not a green
qualification window. The proof folder also retains the first raw-hold refusal
and the Windows SQLite cleanup failure encountered while developing the reader;
the latter was fixed by explicitly closing the read-only connection.

## Next high-difficulty work

Legacy/joint PLACE must target the measured attached point while preserving the
four-DOF position-only solver, collision scene, limits and sole motion executor.
A static 160 mm tweak or only a nonzero `target_point_offset` is insufficient;
#76 already established the latter KDL compatibility failure. Runtime pre-attach
and release coverage also need supported fixes with counterexamples and a new
frozen declaration. Keep all existing stopped records and unchanged gates.
The bounded reporter, ledger and CI tasks remain in #82/#83/#84/#87.
