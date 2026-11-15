# Pose and action-phase timeline (read-only)

`scripts/pose_stage_timeline.py` turns a run's observation stream plus its action-phase records
into one timeline: every pose sample annotated with the phase that was in effect at it, the raw
sampling interval, the boundary offset between the two clocks, and the age of the phase record that
governs it. Where the evidence does not support an alignment it says so, row by row, instead of
inventing a boundary.

## Why this needs to be computed once, carefully

Action phases and world-state observations arrive on different channels. A phase record carries the
stamp of when the action switched; an observation carries the stamp of when the state was sampled;
both are received on the host at a third moment, on a third clock. Deriving "which phase was this
sample in" ad hoc invites two mistakes: interpolating a boundary so that it looks precise, and
counting the same snapshot twice. Both are refusals in this tool.

The duplicate case is not hypothetical: `scripts/diagnostics/record_world_state.py` records the same
world state once from the topic subscription and once from an action result, and labels them with
`channel`. The identical snapshot then appears twice with two receipt stamps. It is one
measurement, so only the first copy is counted.

## Definitions

| output field | definition |
| --- | --- |
| `phase` | the last phase record whose source stamp is at or before the sample's source stamp. Causal, never interpolated; empty when no such record exists. |
| `source_stamp_ns` | the stamp the sample itself carries (simulator / ROS clock). |
| `recv_stamp_ns` | the host receipt stamp. A different clock domain from the source. |
| `offset_ms` | `(recv - source) / 1e6`, raw and possibly negative. It is a boundary offset between two clocks, not a latency claim. |
| `x`, `y`, `z` | the sample pose as recorded; `z` is empty when the sample only carries a plane. |
| `delta_from_prev` | Euclidean distance from the previous **counted** sample, over the coordinates both carry. Empty for the first counted row and for every row that is not counted: an unverified boundary is not measured. |
| `dup_of` | the 1-based row of the kept copy when this row is a duplicate snapshot; empty otherwise. |
| `interval_ns` | source-stamp difference to the previous row in file order. Raw: it may be zero (duplicate stamp) or negative (out of order) and is never clamped or resampled. |
| `freshness_s` | source-clock age of the phase record governing this sample, `(sample - phase) / 1e9`. It is the honest resolution of the phase boundary: we do not tighten it by interpolation. |
| `alignable` | `true` only when every check below passes. |
| `reason` | the primary code when `alignable` is false; empty otherwise. |

`freshness_s` and `offset_ms` are deliberately different quantities. `offset_ms` spans two clock
domains, so it is reported raw and never converted into an age; `freshness_s` stays inside the source
clock and is the only one of the two that can be called an age.

## Which phase applies, and how precise the boundary is

A sample belongs to the last phase record at or before its source stamp. A phase that starts between
two samples is therefore known only to the width of that gap. `summary.json` reports this per
boundary in `phase_boundaries`: the row of the last sample before, the row of the first sample after,
and `window_ns` - the raw gap between them. No row is created at the boundary, nothing is
interpolated, and `window_ns` is not narrowed.

## Input contract

`RUN` is a directory. The two inputs are found in this order, or passed explicitly with
`--observations` / `--phases` (absolute or run-relative):

| input | candidates |
| --- | --- |
| observations | `observations.jsonl`, `world_state.jsonl`, `poses.jsonl`, `data/observations.jsonl` |
| phases | `phases.jsonl`, `stages.jsonl`, `action_phases.jsonl`, `data/phases.jsonl` |

Observation rows (one JSON object per line):

| meaning | fields |
| --- | --- |
| source stamp (integer ns) | `source_stamp_ns`, `stamp_ns`, `header_stamp_ns`, `sim_ns` |
| receipt stamp (integer ns, optional) | `recv_stamp_ns`, `observed_monotonic_ns`, `rx_mono_ns`, `monotonic_ns`, `recv_ns` |
| pose | `pose` or `position`, holding `x`/`y`/`z` or `[x, y(, z)]`; or flat `x`/`y`/`z` in the row |

Phase rows: a non-empty name in `phase`, `stage` or `name`, plus an integer source stamp from the
same field list as observations; `recv_stamp_ns` is optional.

Refused with exit 2 and a message on stderr, rather than guessed at: a missing or empty input file,
a line that is not JSON, a line that is not an object, a phase row without a name or without an
integer stamp, an empty phase file, and a stream where not one row carries an integer source stamp
(that is a contract mismatch, not an unalignable run).

`NaN` / `Infinity` JSON literals are accepted on read - real archives contain them - and become
`NON_FINITE_POSE`.

## Output contract

A new directory (`--out`, must not exist; default `<run>-timeline-<UTC>`) containing
`timeline.csv` and `summary.json`. Rows keep the input's file order: an out-of-order sample stays
where it arrived, marked, rather than being silently reordered.

```
index, phase, source_stamp_ns, recv_stamp_ns, offset_ms, x, y, z, delta_from_prev, dup_of,
interval_ns, freshness_s, alignable, reason
```

`index` is the 1-based input row and is what `dup_of` refers to. The remaining columns are the ones
the issue asks for, in its order.

`summary.json` keys: `rows_total`, `rows_counted`, `rows_unalignable`, `reasons` (primary code
counts), `duplicates` (`copies`, `conflicting_stamps`), `phases` (rows and first/last source
stamp per phase), `phase_records`, `phase_boundaries`, `sampling` (min/median/max of positive
counted intervals, span, zero intervals), `offset_ms` (min/max/negative count), `freshness_s`
(min/max over counted rows), the input paths with sha256, and the deliberate negations
`interpolation="none"`, `resampling="none"`, `row_creation="none"`, `causality_claim=false`,
`independent_acceptance_claim=false`.

### Reason codes

`alignable=false` takes the first applicable code from this priority list; the run is never counted
twice for one row.

| code | meaning |
| --- | --- |
| `MISSING_SOURCE_STAMP` | no integer source stamp on the row |
| `NON_FINITE_POSE` | pose contains NaN / Infinity |
| `MISSING_POSE` | no pose on the row |
| `DUPLICATE_COPY` | same source stamp **and** same pose as an earlier row: one measurement, counted once |
| `DUPLICATE_SOURCE_STAMP` | same source stamp, different pose: a conflicting measurement, not a copy |
| `OUT_OF_ORDER` | source stamp earlier than the last counted sample |
| `CLOCK_ROLLBACK` | receipt stamp earlier than the previous row's receipt stamp |
| `NO_PHASE_YET` | no phase record at or before the sample |

## The six fixture groups

Each group is a fixture in `scripts/test_pose_stage_timeline.py` and the test asserts the values
below.

| group | fixture | asserted result |
| --- | --- | --- |
| normal | 5 samples 100 ms apart, phases `APPROACH` at 0 and `STROKE` at 300 ms | 5 counted; phases 3 + 2; every interval 100 ms; `delta_from_prev` 10 mm; `freshness_s` 0.0/0.1/0.2 then 0.0/0.1; `offset_ms` 5.0; `STROKE` boundary window 100 ms |
| duplicate copy | 4 rows, the third identical to the second with a later receipt | third row `dup_of=2`, `DUPLICATE_COPY`, not counted; 3 counted; `duplicates.copies=1`; `interval_ns=0` kept as the raw fact |
| out of order | 4 rows, third one earlier than the second | third row `OUT_OF_ORDER`, `interval_ns=-100000000` preserved; 3 counted |
| clock rollback | third row received 150 ms before its own source stamp | `CLOCK_ROLLBACK`, `offset_ms=-150.0`; the stream counts again on the next monotonic row; `offset_ms.negative=1` |
| missing phase | 4 samples, the first phase record at 200 ms | first two `NO_PHASE_YET`, the rest `APPROACH` with `freshness_s` 0.0 and 0.1; 2 counted |
| missing pose | one row without a pose, one with `NaN` | `MISSING_POSE` and `NON_FINITE_POSE`; 2 counted |

A seventh fixture covers the conflicting-stamp case (`DUPLICATE_SOURCE_STAMP`, `dup_of` empty), and
a further one asserts that nothing is interpolated: one output row per input row, every
`interval_ns` equal to the raw source-stamp difference, and the phase boundary at 150 ms reported
with a 100 ms window rather than a narrowed one.

## Example

A 7-row fixture with two phases, one duplicate copy, one row without a pose and one out-of-order row:

```
$ python scripts/pose_stage_timeline.py RUN
{"kind": "POSE_STAGE_TIMELINE", "rows_total": 7, "rows_counted": 4, "rows_unalignable": 3,
 "out": "...\\run-002-timeline-20261115T172649Z"}

timeline.csv
index,phase,source_stamp_ns,recv_stamp_ns,offset_ms,x,y,z,delta_from_prev,dup_of,interval_ns,freshness_s,alignable,reason
1,APPROACH,1700000000000000000,1700000000005000000,5.0,0.2,0.1,0.0175,,,,0.0,true,
2,APPROACH,1700000000100000000,1700000000105000000,5.0,0.21,0.1,0.0175,0.009999999999999981,,100000000,0.1,true,
3,,1700000000100000000,1700000000109000000,9.0,0.21,0.1,0.0175,,2,0,,false,DUPLICATE_COPY
4,STROKE,1700000000150000000,1700000000155000000,5.0,0.215,0.1,0.0175,0.0050000000000000044,,50000000,0.0,true,
5,,1700000000200000000,1700000000205000000,5.0,,,,,,50000000,,false,MISSING_POSE
6,STROKE,1700000000250000000,1700000000255000000,5.0,0.22,0.1,0.0175,0.0050000000000000044,,50000000,0.1,true,
7,,1700000000225000000,1700000000230000000,5.0,0.218,0.1,0.0175,,,-25000000,,false,OUT_OF_ORDER
```

`summary.json` for that run: `rows_counted=4`, `rows_unalignable=3`,
`reasons={DUPLICATE_COPY:1, MISSING_POSE:1, OUT_OF_ORDER:1}`, `duplicates.copies=1`,
`phases={APPROACH:2, STROKE:2}`, `sampling={counted:3, min:50 ms, median:50 ms, max:100 ms,
span:250 ms}`, `offset_ms={min:5.0, max:9.0, negative:0}`, `freshness_s={min:0.0, max:0.1}`,
`STROKE` boundary `window_ns=50000000, bounded=true`, `inputs_unchanged=true`.

## What this tool deliberately does not do

- No causality: two things inside one time window are not evidence that one caused the other.
  `causality_claim=false` is written into the summary so it cannot be quoted as one.
- No acceptance: no contact, physics or task verdict; `independent_acceptance_claim=false`.
- No interpolation and no resampling: no pose is synthesised, no row is created at a boundary, and
  the raw interval and phase age are kept as they are.
- No writes to the inputs: both sha256 are recorded and re-checked; a mismatch is an error.
- No Dashboard, no ROS, no third-party dependency.

## Self-verification

Run from the repository root, with the interpreter that ships with this host (no pytest, no ROS):

```
& "C:\Users\fuker\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" scripts\test_pose_stage_timeline.py
```

Observed output (Windows, Python 3.12.14):

```
Ran 22 tests in 0.237s
OK
pose_stage_timeline fixtures: 21 cases, 39 observation rows written, 0 assertions failed
reason codes exercised: CLOCK_ROLLBACK, DUPLICATE_COPY, DUPLICATE_SOURCE_STAMP, MISSING_POSE, NON_FINITE_POSE, NO_PHASE_YET, OUT_OF_ORDER
alignment groups: normal, duplicate_copy, out_of_order, clock_rollback, missing_phase, missing_pose (+ conflicting_stamp, no_interpolation, refused inputs)
```

Exit code 0. A failing assertion makes the script exit 1 (verified by injecting a failing test
in-process: `successful=False` -> `would_return=1`). The same file additionally asserts, every run: the input directory's sha256 is identical
before and after; the output directory did not exist and contains exactly `timeline.csv` and
`summary.json`; an existing `--out` is refused with exit 2 and left untouched; two default runs
produce two distinct directories and byte-identical CSVs; and the output contains no key naming a
pass/fail, causality or contact outcome.

## Limits

- Only synthetic fixtures have been run here. Real archived streams were not available in this sparse
  checkout (`setup/acceptance` and `experiments/` are not present); running a real archive through
  it is a separate read-only step.
- The input is flat JSONL. A nested archive - `record_world_state.py` writes
  `{"channel": .., "rx_mono_ns": .., "world_state": {"header": {"stamp": ..}, "objects": [..]}}` -
  needs a projection step first, including a decision about which object's pose is the sample. The
  tool refuses such a file with exit 2 rather than emitting an all-unalignable timeline.
- Phase rows are aligned by source stamp only. If the phase stream and the observation stream use
  different clocks, the alignment is misaligned by that offset; `offset_ms` makes the difference
  visible but does not correct it.
