# Native audit object lifetime

The next high-value task is the native five-cycle reader timing failure. CI run
41116653853, source c2583ae, stopped after cycle index 2 release with a 787.690270 ms
stale common sample. Its two complete raw streams each contain 30,716 consecutive
2 ms steps; the largest producer interval is 105.222464 ms. The old failure remains
STOPPED. Its exact reader pause source is UNKNOWN because it recorded neither a
failure stack nor a selected common tick.

One local diagnostic baseline on frozen source 19caa01 completed all five cycles.
It measured a 362.705794 ms generation-2 GC pause inside a 385.436406 ms live
collection in cycle index 1 settle. The worker retains the previous whole-file
physics/contact JSON graphs in p_rows/c_rows throughout the following live cycle.
This is a demonstrated lifetime defect and a source of observer delay; it does not
prove the cause of the historical CI error. GC pauses in detached full audits
reached 1.672722995 s. Diagnostic instrumentation is separately hashed.

## Chosen design

Give the existing full-prefix audit a function scope. Keep complete-line parsing,
duplicate rejection, contact validation and verify_cycle unchanged. Return only
the existing scalar summary, so all whole-prefix JSON graphs die before opening
the next cycle's follower. Keep the complete raw files and the final verify_run.
On any worker failure, retain the monotonic failure time, traceback and a read-only
snapshot of follower tables/file positions. Diagnostic failure must not replace the
original exception.

Moving audits to child processes would also isolate memory, but adds serialization
and process termination paths without evidence that reference-count release is
insufficient. Disabling GC or changing freshness evaluation would change global
runtime behavior or permit blind intervals; neither is in scope.

## Acceptance and limits

- A worker-level weak-reference counterexample must fail before the fix: completed
  audit rows remain alive when the next follower is created. Afterward none remain.
- A failed worker must retain its original error plus clock, stack and follower
  snapshot. Existing unready/old-candidate/stale-producer rejection remains intact.
- Run the relevant tests, the complete offline suite and the existing static scan.
- Freeze a new source/declaration and run exactly one five-cycle diagnostic window.
  Independently replay all raw gates; preserve all outcomes and process cleanup.
- Compare active collect/GC durations as measurements, not a latency guarantee or
  CI reproduction. Do not claim that an intermittent CI failure is eradicated.
- Retain 500 ms freshness, first eligible candidate, 2 ms raw continuity, 20 ms bind,
  10 s attachment, 2 mm/1 degree follow, ownership probes and no replacements.
- D3 remains NO_GO, default backend unchanged, moving-arm and true legacy matrix
  qualification remain separate. Junior issues #82/#83/#84 stay delegated.
