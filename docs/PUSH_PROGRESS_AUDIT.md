# Push progress vs net displacement (read-only audit)

`scripts/push_progress_audit.py` reads a run's per-attempt PushObject results and writes, for
every attempt, three numbers: what the skill reported as progress, what the object's own poses say
it actually moved, and the difference between them. It writes diagnostic facts only. It never
prints, and never writes, a verdict about the task.

## Why two numbers and not one

"Progress" in a push archive is what each attempt reports as displacement along the commanded
direction; the retry policy accumulates those reports. "Net displacement" is where the object ended
up between the endpoint poses. They agree only while every attempt moves forward.

`src/flexcell/flexcell_skills/flexcell_skills/contracts/push_recover.py` records the measured
reason they diverge: `accumulate()` counts an attempt that moved the object backwards as **zero**,
never as a negative. Its module docstring reports three of five trials "recovering" while the block
travelled away from the goal. An accumulated progress number is therefore an upper bound on motion,
not a measurement of it - and the two must be read next to each other, not in isolation.

The tool does not re-implement that judgement. It imports `classify_attempt`, `is_progress` and
`MIN_DISPLACEMENT_M` from the frozen contract module (which imports only `math`, so it works
without ROS), and the test file asserts the imported functions are the same objects. The
`reported_counted_m` column is literally what `push_recover.accumulate` would add for that row.

## Definitions

| output field | definition |
| --- | --- |
| `reported_progress_m` | displacement the skill reported for that attempt, signed. Taken from `displacement_along_direction_m` when present (`signed_source=along`), otherwise from `displacement_m` (`signed_source=fallback`), which is an unsigned magnitude and is flagged as such. |
| `reported_counted_m` | what the policy would count: `classify_attempt()`'s third return value. Backwards, carry-engaged and unreadable attempts contribute 0.0. |
| `signed_net_m` | that attempt's own before/after pose pair, projected onto the task direction. Measured independently of the reported field. |
| `difference_m` | `reported_progress_m - signed_net_m`. Empty when either side is unknown. |
| `sign` | `POSITIVE` / `NEGATIVE` only when the measured projection clears `MIN_DISPLACEMENT_M`; otherwise `UNKNOWN` with the measured reason in `net_code`. |
| `difference_total_m` | `sum(reported_progress_m) - signed_net_total_m`; empty unless the report is complete and the net is measured. |
| `counted_minus_net_m` | `sum(reported_counted_m) - signed_net_total_m`: the accumulation error the policy would introduce. |
| `net_measurable` | the run net was measured from the endpoint poses, independently of the report |
| `reporting_complete` | every attempt carried a usable reported displacement |
| `comparison_complete` | both sides exist, so `difference_total_m` is a real comparison rather than a partial sum |
| `missing` | the comparison inputs that are absent (`reported_progress_m`, `signed_net_m`, or both) |

A measurable net is not a completed audit. When an attempt carries no usable reported displacement,
`signed_net_total_m` and `sign` are still reported (they are genuinely measured), while
`comparison_complete=false`, `missing` names the gap and the overall code becomes
`INCOMPLETE_REPORT`. The two halves of the comparison are reported apart instead of one standing in
for the other.

`MIN_DISPLACEMENT_M` (5 mm, from the contract) is reused as the noise floor for sign assignment and
for "off by more than the floor" counts. No new threshold is introduced.

## Direction

`--direction dx,dy` accepts any planar direction; it is normalised before projection, so
`--direction 0.6,0.8` and `--direction 3,4` give the same answer. Without it, the direction is
derived from the first before-pose and the last after-pose and marked `direction_source=derived`.

A derived direction is honest but weak, and the summary says so in `caveats`: the displacement is
projected onto a direction estimated from that very displacement, so a derived sign cannot
contradict itself. Use `--direction` when the sign matters.

## Input contract

`RUN` is a directory. The attempts file is found in this order (or pass `--attempts`, absolute or
run-relative):

1. `push_attempts.jsonl`
2. `attempts.jsonl`
3. `contact_push.jsonl`
4. `skills/push.jsonl`
5. `skills/push_object.jsonl`

One JSON object per line. Recognised fields, first match wins:

| meaning | fields |
| --- | --- |
| signed displacement (preferred) | `displacement_along_direction_m`, `along_m` |
| unsigned magnitude (fallback, marked) | `displacement_m`, `stroke_displacement_m` |
| contact made | `contact_made` |
| carry engaged | `carry_engaged_during` |
| pose before the attempt | `measured_before`, `pre_pose`, `start_pose`, `before_pose`, `before` |
| pose after the attempt | `measured_after`, `post_pose`, `end_pose`, `after_pose`, `after` |
| object identity (guard) | `object_name` |

A pose may be a ROS-style `{"position": {"x": .., "y": ..}}`, a flat `{"x": .., "y": ..}` or a
`[x, y]` list. `NaN` / `Infinity` JSON literals are accepted on read, because
`contact_push_server.py` initialises the displacement fields to NaN before it measures them; they
become `UNKNOWN`, never a silent zero.

The aliases are mapped onto the contract's canonical fields before the frozen
`classify_attempt()` sees the row (`along_m` -> `displacement_along_direction_m`,
`stroke_displacement_m` -> `displacement_m`). There is exactly one interpretation: the row the
contract classifies is the row the CSV quotes, so an archive written with `along_m` is judged as
having progress instead of being read by the audit and dropped by the policy. The original row is
never modified. A row carrying both spellings with **different** values is refused (exit 2), because
choosing one of two answers is exactly the ambiguity this tool exists to expose.

A JSONL line is allowed to be any JSON value. A line that is not an object keeps its
`UNREADABLE_RESULT` report code and `MISSING_ENDPOINT` measurement code, and the rest of the file is
still audited and summarised: a mixed file is diagnosed, not crashed.

The tool refuses (exit 2, message on stderr) rather than guessing: a missing or empty attempts file,
a line that is not JSON, a file where no row carries any recognised field, a run whose attempts span
more than one `object_name`, and a row whose canonical field and alias disagree. Rows whose object
identity is absent are accepted.

## Output contract

A new directory (`--out`, must not exist; default `<run>-audit-<UTC>`) containing two files.
`mkdir(exist_ok=False)` is used, so an existing directory is an error, never an overwrite.

`attempts.csv` columns:

```
index, reported_progress_m, reported_counted_m, signed_source, signed_net_m, difference_m,
sign, code, net_code, contact_made, carry_engaged_during, clears_floor
```

`code` is the contract's own classification of the report; `net_code` is the independent
measurement's status. They are separate columns because "the report is unusable" and "the object did
not move" are different statements.

`summary.json` carries the totals, the direction and its source, the endpoints (row numbers and
poses), `signed_source_counts`, `reasons` (every code seen, with counts), `caveats`, the input
paths with their sha256, and the deliberate negatives `task_success_claim=false`,
`independent_acceptance_claim=false`, `policy_modified=false`, `interpolation_used=false`.

### Status, sign and reason codes

`status` is `MEASURED` only when `code == "OK"`, i.e. when the net is measured **and** the report
is complete; every other code means at least one piece of evidence could not support the comparison.
`sign` is a statement about the measured projection and can be `POSITIVE` while `status` is
`UNKNOWN` (for example: the net is measurable but the report contains a NaN, or an attempt reported
no displacement at all).

| code | meaning |
| --- | --- |
| `OK` | measured, and the projection clears the floor |
| `NO_MOTION` | measured planar motion below `MIN_DISPLACEMENT_M`; a sign would be noise |
| `ZERO_PROJECTION` | the object moved, but not along the direction (lateral) |
| `MISSING_ENDPOINT` | a pose needed for the window is absent |
| `NON_FINITE` | a pose or displacement is NaN / Infinity |
| `NO_DIRECTION` | no direction was given and none could be derived |
| `CARRIED` | carry engaged during the attempt: motion is not explained by contact |
| `MOVED_BACKWARDS` | the reported signed displacement is negative |
| `MISSING_REPORTED` | neither displacement field is present |
| `NON_FINITE_REPORT` | the reported displacement is NaN / Infinity |
| `UNREADABLE_RESULT` | the JSON line is not an object the contract can read |
| `INCOMPLETE_REPORT` | an attempt carried no usable reported displacement, so the comparison is partial even though the net may be measured |

When several codes apply, `code` is the most fundamental blocker in the order `NO_DIRECTION`,
`NON_FINITE`, `MISSING_ENDPOINT`, `INCOMPLETE_REPORT`, then the measurement status
(`NO_MOTION` / `ZERO_PROJECTION` / `OK`). Every code still appears in `reasons`.

## The six boundary classes

Each class is a fixture in `scripts/test_push_progress_audit.py` and the test asserts the numbers
below, so this table cannot drift from the code without a failure.

| class | fixture motion | measured result |
| --- | --- | --- |
| forward | 3 attempts along `(0.6, 0.8)`, one of them backwards 8 mm | `MEASURED`, `POSITIVE`; net +53 mm, reported 53 mm, counted 61 mm, counted - net = +8 mm |
| backward | 2 attempts, -20 mm then -10 mm along `(1, 0)` | `MEASURED`, `NEGATIVE`; net -30 mm, counted 0 mm, counted - net = +30 mm |
| lateral | object moves 30 + 20 mm along +y while direction is `(1, 0)` | `UNKNOWN` / `ZERO_PROJECTION`; net measured as 0.0, sign undefined |
| static | identical before/after poses, reported 0 | `UNKNOWN` / `NO_MOTION`; net measured as 0.0 |
| missing endpoint | last attempt never returned a post pose | `UNKNOWN` / `MISSING_ENDPOINT`; `partial_window` reports the sub-window (rows 1-2) and is labelled as not the run net |
| non-finite | `NaN` literal in the last attempt's displacement | `UNKNOWN` / `NON_FINITE`; net still measured (53 mm), `reported_total_complete=false`, `difference_total_m=null` |

Two further fixtures cover the fallback paths: `signed_source=fallback` over three attempts (the
unsigned magnitudes report +69 mm against a real net of +53 mm, i.e. a hidden backwards attempt makes
the fallback over-report by 16 mm), and a deliberately over-reported attempt (40 mm claimed against
25 mm measured, difference +15 mm, counted in
`rows_reported_off_by_more_than_floor`).

Five regression fixtures guard the boundaries found in review:

| fixture | asserted result |
| --- | --- |
| alias only (`along_m` alone) | the contract sees it: `reported_counted_m=0.03`, `code=OK`, `contact_made=true` (before the fix: counted 0, `MISSING_REPORTED`, contact flipped to false) |
| alias and canonical agreeing | accepted, counted once |
| alias and canonical disagreeing | refused with exit 2 naming both spellings; no silent preference |
| poses only, no reported displacement | `status=UNKNOWN`, `code=INCOMPLETE_REPORT`, but `sign=POSITIVE` and `signed_net_total_m=0.03` preserved, `missing=["reported_progress_m"]` |
| valid row followed by `null` | exit 0 with a summary: row 2 is `UNREADABLE_RESULT` / `MISSING_ENDPOINT`, run code `MISSING_ENDPOINT` (before the fix: TypeError, exit 1, no summary) |

## Example

A three-attempt fixture (the "forward" case above), direction `0.6,0.8`:

```
$ python scripts/push_progress_audit.py RUN --direction 0.6,0.8
{"kind": "PUSH_PROGRESS_AUDIT", "status": "MEASURED", "sign": "POSITIVE", "code": "OK",
 "net_measurable": true, "comparison_complete": true, "missing": [], "attempts": 3,
 "signed_net_total_m": 0.05299999999999999,
 "out": "...\\run-001-audit-20261115T172639Z"}

attempts.csv
index,reported_progress_m,reported_counted_m,signed_source,signed_net_m,difference_m,sign,code,net_code,contact_made,carry_engaged_during,clears_floor
1,0.031,0.031,along,0.03099999999999998,2.0816681711721685e-17,POSITIVE,OK,OK,true,false,true
2,-0.008,0.0,along,-0.007999999999999991,-8.673617379884035e-18,NEGATIVE,MOVED_BACKWARDS,OK,true,false,false
3,0.03,0.03,along,0.030000000000000006,-6.938893903907228e-18,POSITIVE,OK,OK,true,false,true
```

The reported total (0.053 m) happens to equal the net here; the number a retry loop would accumulate
(0.061 m) does not, because attempt 2 moved the object 8 mm backwards and the policy counted that as
zero. That 8 mm is `counted_minus_net_m` in `summary.json`.

## What this tool deliberately does not do

- No task outcome. No pass/fail, no "recovered", no acceptance claim; the output states
  `task_success_claim=false` and `independent_acceptance_claim=false` as data.
- No policy change and no threshold of its own: the only thresholds are the contract's
  `MIN_DISPLACEMENT_M` and the sign rule built from it.
- No interpolation, no fabricated poses, no resampling.
- No writes to the run. Both the before and after sha256 of the attempts file are recorded and
  compared; a mismatch is an error.
- No ROS, no simulator, no third-party dependency. Standard library only, and the single repository
  import is the frozen contract module.

## Self-verification

Run from the repository root, with the interpreter that ships with this host (no pytest, no ROS):

```
& "C:\Users\fuker\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" scripts\test_push_progress_audit.py
```

Observed output (Windows, Python 3.12.14):

```
Ran 32 tests in 0.253s
OK
push_progress_audit fixtures: 29 cases, 34 attempt rows written, 0 assertions failed
reason codes exercised: CARRIED, INCOMPLETE_REPORT, MISSING_ENDPOINT, MISSING_REPORTED, MOVED_BACKWARDS, NON_FINITE, NON_FINITE_REPORT, NO_MOTION, OK, UNREADABLE_RESULT, ZERO_PROJECTION
boundary classes: forward, backward, lateral, static, missing_endpoint, non_finite (+ fallback, derived, over-report, unreadable, carried, refused inputs)
```

Exit code 0. A failing assertion makes the script exit 1 (verified by injecting a failing test
in-process: `successful=False` -> `would_return=1`). The same file additionally asserts, every run: the run directory's sha256 is identical
before and after; the output directory did not exist and contains exactly `attempts.csv` and
`summary.json`; an existing `--out` is refused with exit 2 and left untouched; two default runs
produce two distinct directories; repeated audits are byte-identical; and the output contains no
key named pass/fail/success/verdict/conclusion.

## Limits

- Only synthetic fixtures have been run here. Real archived runs were not available in this sparse
  checkout (`setup/acceptance` and `experiments/` are not present); validating against a real run
  is a separate read-only step.
- The input is flat JSONL. A nested archive (`scripts/diagnostics/record_world_state.py` writes
  `{"world_state": {...}}` rows) needs a projection step first; the tool refuses such a file with
  exit 2 instead of producing an empty audit.
- `displacement_along_direction_m` is assumed to be measured along the direction the caller passes.
  If the run commanded a different direction, the reported and measured columns are not comparable;
  the caveat list does not detect that for you.
