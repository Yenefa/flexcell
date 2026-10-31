# Legacy carry-backend parity — local WSL, 2026-10-31

One manifest (`infra/legacy-parity-window.json`), five declared tasks, executed once
per carry backend on the local WSL stack. Same tasks, same skill backend (MTC), same
**declared 60 mm** placement tolerance, no replacement trials.

| backend | window | cases | worst verified error |
| --- | --- | --- | --- |
| `teleport` | `FUNCTIONAL_WINDOW_PASS` | 4 PASS + 1 EXPECTED_FAILURE | 0.171 mm |
| `velocity_servo` | `FUNCTIONAL_WINDOW_PASS` | 4 PASS + 1 EXPECTED_FAILURE | 0.230 mm |
| `detachable_joint` | `FUNCTIONAL_WINDOW_PASS` | 4 PASS + 1 EXPECTED_FAILURE | **12.252 mm** |

Per case — worst verified error, with the attempt counts that produced it:

| case | teleport | velocity_servo | joint |
| --- | --- | --- | --- |
| normal / A | 0.171 mm (2 picks) | 0.119 mm (1) | 2.202 mm (1) |
| normal / B | 0.093 mm (1) | 0.230 mm (1) | 2.254 mm (1) |
| dual_object | 0.100 mm (3 picks, 2 places) | 0.160 mm (2, 2) | **12.252 mm** (2, 2) |
| recovery_once | 0.090 mm (2) | 0.013 mm (2) | 2.160 mm (2) |
| budget_exhaustion | fails as declared, no place | same | same |

The `budget_exhaustion` case is the declared negative in all three windows: it must
fail with `ERR_RECOVERY_EXHAUSTED`, and it does.

**Reading this honestly — two corrections to the first version of this receipt:**

1. The harness verifies against **60 mm**, not 12 mm. An earlier draft of this file
   (and of the report's default bound) said 12 mm; that was the report's own stricter
   cap, not the declared tolerance, and it should not have been described as the
   tolerance.
2. `dual_object` **does** carry a verified error. It has two places and two
   verifications per run, so this receipt now reports the **worst** of them instead of
   whichever came first — which is where the joint backend's 12.252 mm lives. Taking
   the first or last verification would have reported 0.047 mm for that case and
   hidden the worst placement.

With that correction the accuracy gap is larger than first reported: the joint backend
is ~10x off on the single-object tasks (2.16–2.25 mm) and ~75–120x off on the
dual-object demo (12.252 mm vs 0.100–0.160 mm). Parity of verdict is not parity of
accuracy, and this is a concrete reason to keep the joint backend explicitly selected.

Attempt counts are reported because they differ: `teleport` needed a second PICK on
`normal / A` and three PICKs on `dual_object`, while `velocity_servo` and the joint
backend completed those cases in fewer attempts. The manifest permits recovery, so
this is not a parity failure — but it is a behavioural difference that a
case-level PASS would otherwise hide.

Files: `parity-report.json` (machine comparison), `<backend>/window.json` (as
produced), `<backend>/<run>/skills/{verify,pick,place}.jsonl` (the rows the report
reads, so the numbers can be recomputed without the original machine).

Replay:

```bash
PYTHONPATH=scripts python3 scripts/parity_report.py \
  setup/acceptance/legacy_parity_20261031/*/window.json
```

Scope: one bounded window per backend. This is not a success rate, not a reliability
estimate, and not a D3 admission decision.
