> Correction: endpoint residuals do not establish a physical bound or separate historical population. Raw logs and v1 are unchanged; v2 is the current verifier.

# GRASP-B-001-PHASE-3 — first window with carry telemetry, 2026-10-26

**Current verdict: `FACTS_AND_SUPPORT_VERIFIED; CAUSE_UNKNOWN`**

The original population-separation verdict is withdrawn; see the correction below.

**Historical verdict (superseded): `NOT_REPRODUCED_IN_THIS_WINDOW`** — the historical failure population
was not reproduced. What *was* found is a different, narrower thing: **the box
never really follows the gripper.** It trails its pinned pose by 3–72 mm, and the
window's single failure is simply the worst case of that trailing.

Ten declared trials on a cold-started stack on the WSL execution host:
`A1` → `A4` → `B5`, one object each, run at source `c37af8d` (includes #49
session identity and #50 teleport loop observation). No model service, no GPU,
no retries, no sampling expansion.

| segment | object | trials | succeeded | rise min … max |
| --- | --- | --- | --- | --- |
| A1 | `target_box_a` | 1 | 1 | +0.0719 |
| A4 | `target_box_a` | 4 | 4 | +0.0594 … +0.0971 |
| B5 | `target_box_b` | 5 | 4 | +0.0234 … +0.0936 |

Strict health clean before and after (19 checks, `hard_fail=[]`, `task_state
IDLE`, `carry_engaged False`). World sha `c81c3c09…`, the same world #47 ran.

```bash
python3 setup/acceptance/grasp_phase3_window_20261026/verify_phase3_window.py
python3 setup/acceptance/grasp_phase3_window_20261026/selftest_verify_phase3_window.py
```

`verify_phase3_window.py` asserts every number below and exits 1 if the archive
stops supporting it. `selftest_verify_phase3_window.py` mutates eight private
copies of the archive and requires eight rejections.

## What the two leading hypotheses did not survive

The point of #50 was to see inside the carry servo loop. It does. In this window
the loop recorded **639 end-effector lookups, 0 missing, 639 pin requests, 638
confirmed, 1 rejected**.

| hypothesis | what the data says |
| --- | --- |
| `_ee()` silently returns `None`, skipping pinning | **Dead.** Zero missing lookups in ten trials, including the failing one. |
| pin requests silently fail under teleport | **Dead.** Exactly one rejected request in the window, and it was in a trial that *succeeded*. |

So both of the mechanisms I proposed as the next investigation before this run
are wrong, and the window cost 8 minutes to find that out rather than argue it.

## The thing that is actually true

For each trial, the box's own `carry_offset` and the carry `start` event's
`offset` match exactly, which gives an unambiguous session per trial — no time
windows, no ambiguity. From that join, back out the end-effector height the pin
was aiming at (`box_after.z − carry_offset.z`) and compare it with the height the
motion server actually reached:

| seg | trial | rise | implied EE | reached EE | lag |
| --- | --- | --- | --- | --- | --- |
| A1 | 1 | +0.0719 | 0.2463 | 0.2794 | −33.1 mm |
| A4 | 1 | +0.0620 | 0.2422 | 0.2735 | −31.3 mm |
| A4 | 2 | +0.0810 | 0.2587 | 0.2728 | −14.1 mm |
| A4 | 3 | +0.0594 | 0.2389 | 0.2746 | −35.7 mm |
| A4 | 4 | +0.0971 | 0.2807 | 0.2800 | **+0.7 mm** |
| B5 | 1 | +0.0838 | 0.2647 | 0.2709 | −6.1 mm |
| B5 | 2 | +0.0234 | 0.2015 | 0.2732 | **−71.7 mm** |
| B5 | 3 | +0.0901 | 0.2734 | 0.2769 | −3.5 mm |
| B5 | 4 | +0.0431 | 0.2179 | 0.2721 | −54.2 mm |
| B5 | 5 | +0.0936 | 0.2672 | 0.2708 | −3.6 mm |

The lag is not a fault state — it is the normal state. Successful trials run from
0.7 mm to 54.2 mm of trailing. The one failure is the largest lag in the window,
and it is the only trial that crossed the 30 mm `box_follow_min_m` threshold as a
result.

The lag has the magnitude of a body in free fall for one pin period:
`0.5 · 9.81 · 0.1² = 49 mm`, against the 71.7 mm observed. That is consistent
with the pin *succeeding* at 10 Hz while the box is pulled back by physics
between pins — the arm is at 0.273 m and the box is sampled wherever in that
cycle the sample happens to land.

**This is a measurement-phase hypothesis, not a proven cause.** Nothing in this
archive measures the box *between* pins; there is one sample per trial. The
number is consistent with free fall over one period and that is all.

## Corrected evidence boundary (2026-10-27)

The +17.4 mm value is arithmetic over ten endpoint observations. It is not a
physical lower bound. Those endpoints are not simultaneous samples, and no
continuous velocity or sampling-phase trace was recorded in this archive.

The failed trial's +0.023416 m rise is **inside** the historical natural code-23
support [−0.010278, +0.029835] m; seven of the 92 historical failures are at or
above it. There are 54 negative rises, but that does not establish a disjoint
population or a different cause. Both causal attribution and common mechanism
remain UNKNOWN. The former separation/lower-bound assertions are withdrawn.

`verify_phase3_window.py` is preserved unchanged as v1. Current verification is
`verify_phase3_window_v2.py`, with ten self-test cases including an upper-tail
mutation accepted by v1 and rejected by v2. A negative-only mutation is also
rejected; contrary to the task-note shorthand, unchanged v1 itself rejects an
all-negative set because it requires exactly 54/92 negatives.

## The gate failed once, and it was my rule, not the data

`gate_v1_one_session_per_segment.py` is kept as the record. It required exactly
one carry session per *segment* and blocked A4, although A4's telemetry was
complete: four trials had produced four starts, four sessions and four final
summaries. The task book asks for "an unambiguous matching teleport session" per
trial, not per segment.

`gate.py` (v2) implements the corrected rule, joins trials to sessions by exact
`carry_offset` equality, and was written **before B5 ran**. A4 was re-gated on its
existing data and passed; B5 passed first time. `A4.gate` holds the v1 failure and
`A4.gate_v2` the corrected verdict. A gate that is edited after it fails is only
honest if the edit and its reason are in the archive, which is why both versions
are here.

## What this buys and what it does not

It buys: the first per-trial view of the carry servo, and a clean falsification of
the two mechanisms that had been carrying the investigation. It also supplies the
identity join (`carry_offset` ↔ `start.offset`) that every future window should
reuse instead of time windows.

It does not buy: a cause. One failure in ten trials, no measurement of the box
between pins, and a historical population that was not reproduced.

## Next window, pre-declared

Sample the box pose continuously through the lift and the settle (read-only
observation at ~20 Hz alongside a single trial) and record each pin's target. If
the box oscillates between the pin target and the target minus ~50 mm, the
phase-alias reading is confirmed and `box_follow_min_m` is measuring a sampling
instant, not a grasp. If the box instead sits smoothly at a constant offset, the
lag is real and the question becomes why the physics holds it back. Both outcomes
need one trial and neither requires touching the carry mechanism.

## Stack state at the end

The stack was **already down** when teardown was attempted. It was alive at
13:00 (`health_after.json`, 19 checks, `ok=true`) and gone by 13:14, with no
shutdown line in any runtime log and no owned pid file left behind. The time of
death is unknown. `stack_stop.json` records that finding rather than claiming a
shutdown this session performed.

None of the archive depends on the stack staying up: every log slice, health
receipt and probe row was taken while it was running.
