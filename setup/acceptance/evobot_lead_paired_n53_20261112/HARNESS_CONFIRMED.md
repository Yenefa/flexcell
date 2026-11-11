# Harness confirmed working on a valid domain — full run relaunched

**Date** 2026-11-12 (round 26). Supersedes `HARNESS_DIAGNOSIS.md`.

## Single isolated trial, domain 200

```
attempt 2: asking for 0.0510 m
  moved 0.0536 m contact=True carry=False
policy stopped: reached {'achieved_m': 0.0926, 'target_m': 0.09}
recovery outcome=1 achieved=0.0926 m attempts=2
captured 2/2 objects
graded: terminal_passed=False failed=['push:target_box_a']
'error creating node' occurrences: 0
```

**The stack starts, the robot pushes, the evaluator grades, and the trial yields real data.** The only fault
was the invalid domain ID.

## What this trial shows, read correctly

| field | value | note |
| --- | --- | --- |
| attempts | 2 | recovery fired; first attempt failed **by construction** |
| achieved | 92.60 mm | inside the frozen [30, 150] mm displacement bound |
| `terminal_passed` | **False** | a **different** sub-clause failed: `push:target_box_a` |

**Displacement passed and the trial still failed.** The four sub-clauses are conjunctive, so a 92.6 mm push
can fail on `|Δz| ≤ 0.020` or the final-pose zone radius. **This is worth remembering against the round-17
claim that only the 69.92 mm band passes** — that inference used displacement alone, and this single trial is
already a counterexample to it: 92.6 mm is not in the 69.92 band, yet the displacement clause passed.

**So round 19's 14.7% per-draw figure is an under-count**: it scored passing by band, not by the full
conjunctive clause, and the trial above shows a 92.6 mm push that clears displacement. That figure fed the
power calculation, which means **n=53/arm was derived from a mis-scored pass rate and should not be trusted**.

## Status

Full 66-trial paired run relaunched on domains 200–205 (`/tmp/paired_v2`). Results go to `RESULT.md` under the
unchanged pre-registration.