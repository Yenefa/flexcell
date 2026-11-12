# V2: keep the return high, before a second pilot

V1 pilot is retained, terminal/full acceptance FAILED: final signed net −56.5 mm.
It initially advanced 29.7 mm, then lost progress during the next return.
Native 5 ms physics aligned with waypoint request/result timestamps shows second
retreat LOWER moved red x +99.232 mm, versus +0.001 mm in the preceding TRANSFER.
The second LIFT also moved it backwards about 18 mm. This refutes robust return
preservation by endpoint clearance alone. Stage B for v1 is **NOT_RUN / REJECTED**.

## New hypothesis and honest interface behavior

The low return endpoint is unnecessary before re-observing and re-approaching.
V2 performs LIFT→TRANSFER during RETREATING and holds above the object; APPROACH
still uses LIFT→TRANSFER→LOWER from a fresh measurement. The frozen contract's
original low retreat target is **not claimed reached**: the adapter returns false
and its actual distance to that low target, with an explicit HIGH_HOLD event.
Frozen core behavior records RETREAT_RESULT=false (and retreat_failed when applicable).
This is not a successful original low-point command; full task acceptance is still
separately decided by the unchanged physical evaluator.

The mode defaults false and is enabled only for feedback. All actual waypoint
failures/cancel/stale-state guards remain. Controller fields stay 30 mm / 5 mm
overdrive / one increment / maximum three attempts. No task or gate changes.

## Pilot and fixed batch

One new `pilot2`, separate output/domain. Feasibility additionally requires all
returns to lose no more than 5 mm, at least 5 mm measured final forward progress,
no protected/carry violation, valid post-return state, and valid no-lift/support
evidence. A passed pilot is not pooled into the confirmatory batch.

Only if this mechanism gate passes, run the original fixed order A1 B1 B2 A2 A3 B3,
with A=previous three-waypoint recovery and B=v2 high-hold feedback. Same world,
image, task and three-attempt budget. The treatment is the combined feedback/
bounded-shot/high-return controller; do not attribute its result to one component.
All six slots are retained, with no favorable replacement or optional stopping.
An infrastructure failure stops collection for diagnosis. Unsafe carry/protected
violations stop the affected run and are reported, never regraded or discarded.
