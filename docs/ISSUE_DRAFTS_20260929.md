# GitHub issue drafts — POSTED

> **Status: POSTED 2026-10-03.** Issue A → [#22](https://github.com/Yenefa/flexcell/issues/22),
> Issue B → [#23](https://github.com/Yenefa/flexcell/issues/23),
> Issue C → [#24](https://github.com/Yenefa/flexcell/issues/24) — posted by the
> desktop-revival session (the original 9/29 posting failure was an invalid
> `gh` token on the laptop; the desktop's `gh` is authenticated). Bodies kept
> below verbatim for provenance.

Prepared 2026-09-29 during the new-machine (RTX 4060 laptop) bring-up +
first official benchmark batch, at `main` = `070aed6`.

---

## Issue A — M3 benchmark cells S3/S4 are not instrumented: the task path

## records no episode and is not on the policy seam

**Labels:** M3, benchmarking, gap

### Problem

`setup/94_scenario_runner.py` advertises five scenarios (S1/S2/S4/S5/S7), but two
of the seven cells in the ratified design (`docs/WEEK2_PREPARATION.md` §4.2) cannot
produce benchmark data:

- **S3 (injected failure, PICK_B first attempt) does not exist at all.** There is
  no `S3` entry in `SCENARIOS`. The only B-capable entry point is the
  `RunPickPlace` task path.
- **S4 (unreachable place target) runs through `RunPickPlace`, which records no
  episode and is not wired to the decision-policy seam.** In
  `flexcell_skills/task_fsm_server.py`, `EpisodeRecorder` is constructed only in
  `_execute_demo` (line ~479). `_execute` (the `RunPickPlace` handler, line ~257)
  has no recorder, no `self._policy.decide(...)`, and no
  `self._episodes.write(...)`. This matches the HANDOFF note "RunPickPlace
  single-object path not on the seam (declared retained)".

### Consequences (measured, not inferred)

1. S4 produces no entry in the replay store, so `95_metrics_report.py` has no
   cell for it, and the runner's own pass criterion
   (`replay_ok is not True` → counted bad) makes any S4 batch report FAIL.
2. `CELL_OF_SCENARIO` in `95_metrics_report.py` only maps `week1_demo_v1`,
   `recovery_demo_v1`, `exhaust_demo_v1`; everything else falls into a `dev/*`
   bucket. S7 (`s7_perturb_v1`) was silently landing in `dev/` — fixed in this
   session by adding the mapping (see below); S3/S4 still have no mapping because
   they record nothing.

### Why it matters for M3

M3's entry gate (ADR-003) requires the treatment arm to run on the same harness.
Cells that cannot emit an episode cannot be compared, and the design's own
n-per-cell targets (S1-S3 × 20→50, S4/S5 × 10→30) cannot be met for S3/S4.

### Proposed work (NOT done in this session — needs its own AC)

1. Decide the seam question first: either bring `RunPickPlace` onto the
   `DecisionPolicy` seam + `EpisodeRecorder` (making S3/S4 first-class), **or**
   formally declare S3/S4 out of the primary track with the reason recorded.
   This is an architecture decision → needs an ADR amendment, not a code tweak.
2. If (1) is "wire it": add S3 to `SCENARIOS` (task run on `target_box_b` with an
   armed `once` injection — note the injection key is `scenario|object_name`, so
   the per-object counter already gives PICK_B its own first-attempt failure), add
   S3/S4 entries to `CELL_OF_SCENARIO`, and keep the Week-1.5 trace-parity bar.
3. Also consider: the runner runs cells sequentially, while §4.2 requires runs
   "interleaved across cells to avoid time-of-day drift". The first official batch
   was sequential; interleaving is a small runner change and should land before
   M3 numbers are quoted.

### Evidence

- Code: `setup/94_scenario_runner.py:42-53` (SCENARIOS), `:172-177` (bad counter),
  `setup/95_metrics_report.py:39-46` (CELL_OF_SCENARIO),
  `src/flexcell/flexcell_skills/flexcell_skills/task_fsm_server.py:257` vs `:479`.
- Design: `docs/WEEK2_PREPARATION.md` §4.2 table (S1..S7, per-cell run targets).
- First official batch on the new machine ran S1/S2/S5/S7 only; S3/S4 are recorded
  as `NOT_RUN` with this root cause in `docs/EXPERIMENTS.md` (E-009).

---

## Issue B — `gz.msgs.Pose` flood: a hard gate that has never been green, and

## the audit claim that it was fixed is unsupported

**Labels:** bug, verification-integrity, M2.3

### Problem

`setup/lib_gate.sh`'s `gate_flood` requires **zero** unregistered-gz-class
tracebacks in reset artifacts. Every run fails it with ~900-1000 of:

```
TypeError: No message class registered for 'gz.msgs.Pose'
  File ".../gz/transport13/__init__.py", line 115, in cb_deserialize
  File ".../flexcell_skills/common.py", line 75, in cb
    for ent in msg.pose:
```

### This is NOT a regression from the new machine — the delivery host's own

### committed evidence contains the same flood

| committed artifact                                                | tracebacks | of which `gz.msgs.Pose` |
| ----------------------------------------------------------------- | ---------- | ----------------------- |
| `setup/acceptance/week15/delivery_20260926/66_reset1.out`         | 1016       | 1016                    |
| `setup/acceptance/week15/att_w15_20260926/61_E0_reset_before.out` | 1030       | 1030                    |
| `setup/acceptance/week15/cs_20260926/cs_reset_before.out`         | 964        | 964                     |
| `setup/acceptance/week2/m2_2_step0_ghost_fix/83b_reset.out`       | 963        | 963                     |

So `gate_flood` has never passed on any recorded run, and the M2.3 audit's claim
that the `common.py` pb2 registration fix is "in place" is not supported by any
evidence that ever satisfied the gate it introduced.

### The registration IS present and still does not work

`flexcell_skills/common.py:64-67` imports `pose_v_pb2, pose_pb2, header_pb2` from
`gz.msgs10` before subscribing with `gz.transport13`. The nested `Pose` class is
still not found at deserialization time, so the versioned-binds pairing
(`gz.msgs10` vs `gz.transport13`) is the prime suspect. Reproduce with a minimal
script before changing the import; a correct fix should make `gate_flood` green.

### Why it is more than cosmetic

The same stream backs `sample_gz_pose`, which the admin `reset` uses to verify
canonical poses. A reset run on the new machine reported:

```
"ok": false, "scene_cleared": false,
"canonical target_box_a": "DRIFT [0.282137, 0.00126, 0.028216]"
```

i.e. the world was **not** restored to canonical after an abort-while-carrying
case, so the next episode starts from a displaced box. This is the known
"reset does not clear attached collision objects" hardening item, and it makes
per-episode cell independence unreliable for long batches. It is the main reason
the first official batch was gated on a _canonical world check_ before starting.

### Evidence

- `setup/acceptance/sessions/week15_battery_070aed6_20260929_000504/*.out` (new
  machine, 899-953 per reset), battery stdout `61_battery.out` (5 GATE FAILs).
- The four committed artifacts tabled above.

---

## Issue C — static scan false positive on class attributes

**Labels:** tooling, bug

### Problem

`setup/82_undefined_attr_check.py` reports:

```
MISSING src/flexcell/flexcell_skills/flexcell_skills/jev_backends.py -> self.name
SCAN COMPLETE: 25 files scanned, 1 files with problems
```

### It is a false positive — verified at runtime, not by inspection

`self.name` is a **class attribute** (`name = 'typesafe'`, `name = 'local-reproduction'`).
Verified in the built environment:

```
typesafe -> 'typesafe'            | health: (False, "typesafe-sdk not installed ...")
local    -> 'local-reproduction'  | health: (False, 'FLEXCELL_JEV_ENDPOINT not set ...')
```

### Root cause

The scanner collects `self.X` names only from `ast.Store` context and method
names; a class-body assignment is an `ast.Assign` whose target is a plain `Name`,
so it is invisible to it.

### Requested fix

Make the scanner scope-aware: collect class-body attribute names per class (plus
inherited ones) and count them as assigned for `self.X` uses inside that class.
A gate that cries wolf on the very file (#10) it was supposed to certify trains
people to ignore it.

**Deliberately not done in this session**: editing a verification gate without
explicit sign-off is how audit integrity erodes. The backends are correct and
must not be "fixed".
