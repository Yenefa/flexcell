# The visual gate: frames and truth must be contemporaneous

**Status:** implemented and unit tested offline. No live Gazebo capture has been
put through it, and no run in this repository passes it today (see §9). It is a
gate over records, not a perception result.

Related: [scripts/visual_gate.py](../scripts/visual_gate.py),
[scripts/test_visual_gate.py](../scripts/test_visual_gate.py),
[evobot_visual_vs_truth.py](../setup/acceptance/evobot_visual_capture_20261111/scripts/evobot_visual_vs_truth.py),
[the capture-card README](../setup/acceptance/evobot_visual_capture_20261111/README.md).

## 1. Why "the truth is in the file" is not an acceptance

The pairing tool answers one question per frame: *which ground-truth sample was
taken closest to this capture, and how far away was it*. That answer is
necessary and it is not sufficient, because a report can be true and still be
read as evidence for something it never checked:

| What a pairing file can contain | Why reading it as acceptance is wrong |
| --- | --- |
| `frames_paired: 0` | The file exists, so "frames were paired with truth" is now a sentence someone can write. Nothing was paired. |
| A frame with no `captured_wall_ns` | The pairing is undefined: there is no wall-clock instant to compare a wall-clock sample against. A simulation stamp cannot stand in for one. |
| Truth that never mentions the task object | Every frame can be paired against truth about *some other* object, and the claim "the object was where the run says" stays unmeasured. |
| A pose of `NaN` | The value parses as JSON (the decoder accepts the token) and every comparison against it is meaningless in the same direction. |

Each of those is a run that can currently reach a "visual evidence" paragraph.
The gate makes them non-zero exits with a named reason code instead.

The gate is also the answer to a smaller complaint: the two visual pytest files
used to import the pairing tool from a directory *outside* the repository, so a
plain checkout and CI could not run them at all. The tool now lives in
`setup/acceptance/evobot_visual_capture_20261111/scripts/`; those tests resolve
it there first, fall back to the maintainer's older `ci-public-window` sibling
layout, and skip with the paths they looked at rather than crashing collection.
This document is about the gate that sits on top of the same tool.

## 2. Where the gate sits

```
camera_snapshot.py / record_sim_data.py
        |  frames, and truth sampled next to them
        v
evobot_visual_vs_truth.py            <- pairing report, trajectory for evaluate.py
        |
        v
scripts/visual_gate.py               <- THIS: refuses unless every frame pairs
        |                              and every declared object appears
        v
acceptance claim ("frames and truth are contemporaneous")
```

Three things it deliberately is not:

- **not an evaluator change.** `benchmark/evaluators/evaluate.py` stays frozen;
  its push/place clauses and their trajectory requirement are untouched. The
  gate runs beside the evaluator, not inside it.
- **not a second pairing implementation.** It imports `pair_one` and
  `truth_from_sidecar` from the acceptance tool rather than restating the
  tolerance rules, so "is this sample close enough" has exactly one answer.
- **not a screenshot reviewer.** It never opens an image (§8).

## 3. What it reads

A run directory. Defaults, each overridable by a flag:

| Path | Flag | Required | Contents |
| --- | --- | --- | --- |
| `<run>/data/frames.jsonl` | `--frames` | yes | one frame record per line; must carry `captured_wall_ns` |
| `<run>/data/truth_samples.json` | `--truth` | unless frames carry their own | truth sampling: a list, one sample object, or `{"samples": [...]}` |
| `<run>/data/objects.json` | `--objects a b c` | yes | the object names this run claims to have worked on: a list, or `{"objects": [...]}` |
| `<run>/visual_receipt.json` | `--out` | written only on pass | the receipt (§6) |

A truth sample is `{"wall_ns": <int>, "source": "<name>", "objects": {name:
[x, y, z]}}`. A frame record carrying its own `truth` block (as
`camera_snapshot.py --truth-objects` writes into its sidecar) uses that block in
preference to the external file, because its gap to the frame is the one that was
measured rather than reconstructed.

Frame-record rules:

- `captured_wall_ns` is **required** and must be an integer wall-clock value.
  A simulation stamp (`sim_ns`) or a monotonic clock (`monotonic_ns`) is not a
  substitute: truth is sampled on the wall clock, so comparing across clocks
  produces a number that means nothing.
- `valid: false` marks a capture the recorder itself refused (missing or stale
  telemetry). Such a row is **not** offered as a frame - the same rule the
  pairing tool applies to a sidecar with `ok=false` - and the count is reported
  in the receipt as `frames_skipped_invalid`, so a manifest cannot shed rows
  quietly. A row that says nothing about validity is graded: the absence of a
  refusal is not a refusal.
- `path` names the image; `image` is accepted as the same field under the name
  `data/frames.jsonl` uses. No path is invented for a row that names neither.

Declaring the objects is mandatory. Without a declaration, "the declared objects
appear in the truth" is a check over an empty set, which passes for a run whose
truth mentions nothing at all.

## 4. Exit codes

| Code | Meaning |
| --- | --- |
| 0 | every graded frame paired inside `--max-gap` and every declared object appeared; the receipt was written |
| 1 | refused: a frame failed the gate, or the run has no frames / no truth. Nothing was written |
| 2 | refused to grade: bad invocation or unusable input (missing run directory, malformed manifest or truth file, no declared objects, no pairing tool) |

A receipt exists only for exit 0, so the presence of `visual_receipt.json` is
itself the pass signal. An existing receipt is never overwritten without
`--force`.

## 5. Reason codes

Printed as `FAILED: <CODE> frame=<frame>: <detail>` on stdout for per-frame
failures, and inside the single `REFUSED: <CODE>: ...` line on stderr for
run-level refusals.

| Code | Fired when | What to fix |
| --- | --- | --- |
| `NO_FRAMES` | manifest missing, empty, or every row marked `valid: false` | capture frames; do not substitute an empty manifest |
| `NO_TRUTH_SAMPLES` | no sample in the truth file and no frame carries its own | sample ground truth at capture time |
| `FRAME_WITHOUT_CAPTURE_STAMP` | `captured_wall_ns` absent or not an integer | record the wall clock at capture |
| `FRAME_UNPAIRED` | the pairing tool refused: nearest sample beyond `--max-gap`, or no usable sample | capture truth closer to the frame; do not widen the limit to make a run pass |
| `POSE_NOT_FINITE` | a paired pose is not three finite numbers (NaN, infinity, non-numeric, wrong length) | fix the sampler; the value is not a measurement |
| `OBJECT_MISSING_FROM_TRUTH` | a declared object is absent from the paired truth | declare what the run really watched, or measure the object it claims |
| `NO_DECLARED_OBJECTS` | no `--objects` and no `data/objects.json` | declare the objects |
| `PAIRING_TOOL_NOT_FOUND` | the acceptance tool is in neither documented location | check out `setup/acceptance/` or pass `--pairing-script` |
| `MALFORMED_INPUT` | manifest line is not JSON, truth file is not one of the accepted shapes, `objects.json` is unreadable | write the documented shapes |

## 6. The receipt

`visual_receipt.json`, strict JSON (`allow_nan=False`), sorted keys:

| Field | Meaning |
| --- | --- |
| `record_kind` | `FLEXCELL_VISUAL_GATE_RECEIPT` |
| `frames_in_manifest` / `frames_skipped_invalid` / `frames_seen` | rows parsed / rows the recorder refused / rows graded |
| `frames_paired` | graded rows that paired; equal to `frames_seen` when the file exists |
| `pairing_rate` | `frames_paired / frames_seen`; 1.0 by construction, recorded so the rule is visible in the artefact and not only in the code |
| `max_gap_s` | the limit this run was checked against |
| `max_pairing_gap_s` | the widest frame-to-truth interval that was actually accepted |
| `objects` / `objects_seen` | declared names / names that appeared in the paired truth |
| `truth_sources` | every `source` string among the accepted pairs |
| `frame_evidence` | per frame: capture and truth wall times, gap, objects |
| `visual_appearance_judged` | literal `false` |
| `scope` | the disclaimer below, carried in the file so a reader who finds it alone cannot over-read it |
| `limits` | what the gate did not check |

The scope sentence, verbatim:

> Each entry means: ground-truth object poses were measured within `max_gap_s`
> of the moment this frame was captured, and every object declared for the run
> appears in that truth. This receipt does **NOT** mean the frame was
> interpreted: no pixel was inspected, nothing in it was recognised, and no
> judgement about visual appearance (colour, shape, count, visibility) or about
> whether the robot can see was made.

## 7. Re-running

Full checkout, WSL (ROS 2 Jazzy + pytest):

```bash
cd ~/work/flexcell
# the two visual pytest files: resolve the pairing tool in-repo, no sibling checkout needed
python3 -m pytest -q src/flexcell/flexcell_skills/test/test_visual_truth_pairing.py \
                        src/flexcell/flexcell_skills/test/test_visual_trajectory_clause.py
# the gate's own suite: stdlib only, no pytest, no ROS
python3 scripts/test_visual_gate.py
# the gate itself
python3 scripts/visual_gate.py /path/to/run --objects target_box_a
```

Windows, no ROS and no pytest:

```powershell
python scripts\test_visual_gate.py
python scripts\visual_gate.py C:\path\to\run --objects target_box_a
```

On a sparse checkout that does not carry `setup/acceptance/`, the two pytest
files skip and say which paths they looked at, and the gate's suite runs its
gate cases against a contract stand-in while marking the stand-in-versus-real
comparison as skipped. Neither is a pass for the missing tool: the gate itself
exits 2 with `PAIRING_TOOL_NOT_FOUND`.

## 8. Limits: what this proves, and what it does not

**Proves:** every graded frame has a wall-clock capture time; ground-truth object
poses were measured within `--max-gap` of that time; every declared object
appears in that truth; the receipt records the gaps rather than smoothing them.

**Does not prove:**

- **anything about the image.** No pixel is read. The gate cannot tell a red
  block from a blue one, cannot count objects, cannot segment, and makes no
  claim that the robot can see. A frame could be black, blurry, or of a
  different scene and still pass; what passed is the timestamp bookkeeping.
- **that the image file exists.** The manifest is trusted to describe captures
  that were written; `sha256` and file size are not re-verified here (the camera
  snapshot tool and the pairing report carry those).
- **anything about motion inside a gap.** `--max-gap` defines "the same moment"
  as an interval. A lift that began and ended inside the widest accepted gap is
  invisible, exactly as the sampling limit in the pairing report says.
- **that the task was done.** No displacement, no success, no evaluator clause.
  The gate is an input to acceptance, never the acceptance itself.
- **anything about a live run.** Every case in
  [scripts/test_visual_gate.py](../scripts/test_visual_gate.py) is synthetic: no
  Gazebo, no camera, no truth sampler.

## 9. Current state: no run in this repository passes the gate

`scripts/record_sim_data.py` writes frame rows with `sim_ns` (simulation stamp),
`monotonic_ns` (a monotonic clock) and `image`, and does **not** write
`captured_wall_ns`. The truth sampler samples on the wall clock
(`time.time_ns()`). So the two clocks a run would need to compare are not
recorded on the same basis, and every such row is refused with
`FRAME_WITHOUT_CAPTURE_STAMP`.

That refusal is the gate working, not a defect in it: without a wall-clock
capture time there is no honest way to say which truth sample belongs to a
frame, and accepting the simulation stamp would mean accepting a pairing that
was never measurable. What would change the verdict is a recorder that writes
the wall clock at capture (or frames that come from `camera_snapshot.py`
sidecars, which already carry `captured_wall_ns`). Until then, a visual
acceptance claim in this repository cannot be backed by this gate, and a run
that fails it should be reported as `NOT_GATED`, not as a pass.


## End-to-end result on a real run (2026-11-16)

The gate is no longer theoretical: a camera-enabled `velocity_servo` run produced
the inputs and passed.

```
python3 scripts/sim_smoke.py --out /tmp/237_visual --backend velocity_servo \
  --skill-backend legacy --camera
-> PASS, PICK_A:OK / PLACE_A:OK / VERIFY_A:OK, final_position_error_m = 6.2 mm
-> data/frames.jsonl   593 frames
-> data/truth_samples.json  6,021 samples, objects [target_box_a, target_box_b]

python3 scripts/visual_gate.py <run> --out receipt.json
-> {"ok": true, "frames": 427, "frames_paired": 427, "pairing_rate": 1.0,
    "max_pairing_gap_s": 0.042885, "objects": [target_box_a, target_box_b]}
```

Two changes were needed to get there, and both are about *supply*, not about the
gate's strictness:

1. `scripts/record_sim_data.py` now stamps every frame with `captured_wall_ns`
   and writes `data/truth_samples.json` + `data/objects.json` itself, from the
   per-step physics trace. Before this, no run could ever pass: every frame was
   refused with `FRAME_WITHOUT_CAPTURE_STAMP`.
2. `scripts/frame_reconcile.py` backfills frames recovered from the bag. Those
   now carry a wall stamp **derived** from the real anchors
   (`captured_wall_ns_source = derived_from_anchors`), so a backfilled frame is
   distinguishable from a captured one instead of being silently dropped.

The clock relation is published, not assumed: the trace stamp is monotonic, so
`clock_offset_ns` (measured once at recorder start) is added and recorded in
`truth_samples.json` and `collection.json`.

### What the receipt still does not say

It says every graded frame had ground truth within 43 ms and that the declared
objects appeared in that truth. It does **not** say the robot recognised
anything: no pixel was inspected, `visual_appearance_judged` is false, and the
scope sentence in the receipt states this. A frame whose image is wrong but whose
timing is right still passes - that is a separate check (image hash and content),
and it is not implemented.


## Correction: the capture instant is derived, never assumed (2026-11-16)

A review of this work found a real defect in what feeds the gate, and it is worth
recording because the failure was silent.

`scripts/record_sim_data.py` used to write the **callback** time into
`captured_wall_ns`. The callback runs whenever delivery finishes, not when the
camera captured the image. Measured on this host, that delay is **not small**:

```
capture->receipt delay over 562 frames
  min 89.8 ms | median 2,901.2 ms | max 5,915.3 ms
```

So every frame was being dated up to ~5.9 s after the instant it depicts. A
two-second-delayed frame paired with truth measured two seconds later would look
*perfect* (gap 0) while describing a world that had already moved. The gate was
working correctly on a wrong input, which is the worst kind of pass.

What changed:

- `scripts/capture_time.py` (new, ROS-free) derives the capture instant from the
  frame's **own simulation stamp**, interpolated through the physics trace, which
  records `sim_ns` and the producer's `monotonic_ns` for every step. Those pairs
  are the run's only measured simulation-to-real-clock relation.
- `received_wall_ns` is recorded separately, so the delivery delay stays visible
  instead of being lost.
- A frame whose stamp falls outside the traced range is written with
  `captured_wall_ns = null`, `capture_time_source = UNKNOWN` and a named reason.
  It is not extrapolated: a guess in a manifest is indistinguishable from a
  measurement to whoever reads it next.
- `scripts/visual_gate.py` reports those frames under a distinct code,
  `CAPTURE_TIME_UNKNOWN`, rather than folding them into
  `FRAME_WITHOUT_CAPTURE_STAMP`. "The mapping could not be built" and "nothing
  was recorded" are different facts.

Re-run after the fix, same task and world:

```
562 frames, all capture_time_source = derived_from_physics_trace
visual_gate -> ok, 411 frames paired, pairing_rate 1.0,
               max_pairing_gap_s = 0.0248
```

That 24.8 ms is a *measured* pairing gap. The previous 42.9 ms was measured
against stamps that were themselves wrong.

### The second correction: a refusal must revoke a pass

The same review found that re-checking with `--force` and failing left the old
`visual_receipt.json` in place, unchanged. Since "a receipt exists" is this tool's
pass signal, that reported a pass the current inputs contradict.

A re-check now moves the previous receipt to
`visual_receipt.superseded-<UTC timestamp>.json` immediately before the verdict is
produced, so the pass signal is gone while the history is kept. It does this
*after* every "cannot grade" precondition on purpose: a refusal to grade is not a
verdict about the run, and must not revoke a receipt that the last gradable inputs
supported.
