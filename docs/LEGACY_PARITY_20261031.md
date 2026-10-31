# Legacy parity: same tasks, same tolerance, three backends

Status: declared manifest, one window per backend, executed once on the local stack.
This closes the D3 criterion that `DETACHABLE_ADMISSION_20261027.md` recorded as
PARTIAL ("initial joint/legacy A passed; complete teleport/joint legacy matrix is
absent"). D3 stays **NO_GO**, and the numbers below are one reason why.

## What "parity" is allowed to mean here

Parity is not "the new backend also worked once". It is: the **same manifest**, the
**same skill backend**, the **same declared tolerance**, and the **same verdict**
rule, applied to every carry backend, with no replacement trials and with the
declared negative case (`budget_exhaustion`) still required to fail.

`scripts/parity_report.py` enforces that: it refuses to compare windows with
different `declaration_sha256`, refuses a short case list, and fails the report if
any case is not PASS/EXPECTED_FAILURE or if the verifier's own measured error exceeds
the verifier's own declared tolerance. It never turns a missing case into a pass, and
it reports the attempt counts and the **worst** verified error of each case instead of
flattening them into the verdict.

## Result (`setup/acceptance/legacy_parity_20261031/`)

| backend | window | cases | worst verified error |
| --- | --- | --- | --- |
| `teleport` | `FUNCTIONAL_WINDOW_PASS` | 4 PASS + 1 EXPECTED_FAILURE | 0.171 mm |
| `velocity_servo` | `FUNCTIONAL_WINDOW_PASS` | 4 PASS + 1 EXPECTED_FAILURE | 0.230 mm |
| `detachable_joint` | `FUNCTIONAL_WINDOW_PASS` | 4 PASS + 1 EXPECTED_FAILURE | **12.252 mm** |

Per case (worst verified error, attempt counts in brackets):

| case | teleport | velocity_servo | joint |
| --- | --- | --- | --- |
| normal / A | 0.171 mm (2 picks) | 0.119 mm (1) | 2.202 mm (1) |
| normal / B | 0.093 mm (1) | 0.230 mm (1) | 2.254 mm (1) |
| dual_object | 0.100 mm (3 picks, 2 places) | 0.160 mm (2, 2) | 12.252 mm (2, 2) |
| recovery_once | 0.090 mm (2) | 0.013 mm (2) | 2.160 mm (2) |
| budget_exhaustion | expected failure | expected failure | expected failure |

## Two corrections to the first version of this evidence

1. **The declared tolerance is 60 mm, not 12 mm.** The report originally applied its
   own stricter 12 mm cap and the documentation called that "the tolerance". The cap
   was not wrong as a check — every case was far inside it until the correction below —
   but describing a self-imposed bound as the declared one was.
2. **`dual_object` does carry a verified error, and it is the worst one.** That case
   places two objects and therefore has two verifications per run. The first version
   read a single record and reported "no metric"; reading only the first or only the
   last verification gives 0.047 mm for the joint backend and hides a 12.252 mm
   placement. The report now takes the worst verification of each case.

## The number that matters for the decision

The joint backend **passes**, and it passes with roughly **ten times** the placement
error of the legacy backends on the single-object tasks (2.16–2.25 mm vs
0.013–0.230 mm), and roughly **75–120 times** on the dual-object demo (12.252 mm vs
0.100–0.160 mm).

Parity of verdict is not parity of accuracy. Nothing was relaxed to make the joint
window pass, and this is a concrete reason to keep the joint backend explicitly
selected rather than default.

The 12.252 mm has since been explained, and it is **not** a dual-object-specific
degradation: [the diagnosis](JOINT_PLACEMENT_DIAGNOSIS_20261031.md) shows the box is
released within 0.11 mm of the target and the error is created by the landing after the
declared 12 mm drop — 1.3–2.7 mm at 12 mm clearance, 2.3–9.4 mm at 50 mm. The joint
backend cannot move the box onto the table, only the arm, so its release is a drop while
the legacy backends servo the box down and release it in place. That is the whole gap.

## Boundaries

- One bounded window per backend, one task each. No success rate, no reliability
  estimate, no MTBF.
- The joint window ran without the contact instrumentation and without the
  follow-qualification gate: this is carry-behaviour parity, **not** another D3
  evidence window. The D3 windows with contact/follow gates are separate.
- `teleport` needed a second PICK on `normal / A` and three on `dual_object`; the
  manifest permits recovery, so this is reported, not treated as a failure.
- Default admission remains **NO_GO**; model batches n ≥ 50 stay frozen.
