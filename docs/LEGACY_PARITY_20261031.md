# Legacy parity: same tasks, same threshold, three backends

Status: declared manifest, one window per backend, executed once on the local stack.
This closes the D3 criterion that `DETACHABLE_ADMISSION_20261027.md` recorded as
PARTIAL ("initial joint/legacy A passed; complete teleport/joint legacy matrix is
absent"). D3 stays **NO_GO**, and the numbers below are one reason why.

## What "parity" is allowed to mean here

Parity is not "the new backend also worked once". It is: the **same manifest**, the
**same skill backend**, the **same placement tolerance**, and the **same verdict**
rule, applied to every carry backend, with no replacement trials and with the
declared negative case (`budget_exhaustion`) still required to fail.

`scripts/parity_report.py` enforces exactly that: it refuses to compare windows with
different `declaration_sha256`, refuses a short case list, and fails the report if
any case is not PASS/EXPECTED_FAILURE or if any placement error exceeds the 12 mm
tolerance. It never turns a missing case into a pass.

## Result (`setup/acceptance/legacy_parity_20261031/`)

| backend | window | cases | max placement error |
| --- | --- | --- | --- |
| `teleport` | `FUNCTIONAL_WINDOW_PASS` | 4 PASS + 1 EXPECTED_FAILURE | 0.171 mm |
| `velocity_servo` | `FUNCTIONAL_WINDOW_PASS` | 4 PASS + 1 EXPECTED_FAILURE | 0.230 mm |
| `detachable_joint` | `FUNCTIONAL_WINDOW_PASS` | 4 PASS + 1 EXPECTED_FAILURE | 2.254 mm |

Per case (placement error):

| case | teleport | velocity_servo | joint |
| --- | --- | --- | --- |
| normal / A | 0.171 mm | 0.119 mm | 2.202 mm |
| normal / B | 0.093 mm | 0.230 mm | 2.254 mm |
| dual_object | (no single placement metric) | — | — |
| recovery_once | 0.090 mm | 0.013 mm | 2.160 mm |
| budget_exhaustion | expected failure | expected failure | expected failure |

## The number that matters for the decision

The joint backend **passes**, and it passes with roughly **ten times** the placement
error of the legacy backends. Parity of verdict is not parity of accuracy: on this
window the fixed joint lands the box ~2.2 mm off while teleport/velocity servo land
it within 0.25 mm.

That is not a reason to relax anything, and it is not a reason to promote the joint
backend. It is a reason to keep it explicitly selected, which is what the current
admission already does.

## Boundaries

- One bounded window per backend, one task each. No success rate, no reliability
  estimate, no MTBF.
- The joint window ran without the contact instrumentation and without the
  follow-qualification gate: this is carry-behaviour parity, **not** another D3
  evidence window. The D3 windows with contact/follow gates are separate.
- `dual_object` has no single `final_position_error_m`; it is reported as a pass with
  both objects at their zones, and no error metric is invented for it.
- Default admission remains **NO_GO**; model batches n ≥ 50 stay frozen.
