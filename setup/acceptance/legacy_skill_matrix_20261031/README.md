# Legacy skill matrix — 2026-10-31

`skill_backend=legacy` on both carry backends, same five declared tasks and same 60 mm
verifier tolerance as the MTC windows. Read `docs/LEGACY_SKILL_MATRIX_20261031.md`.

| file | what it is |
| --- | --- |
| `matrix-report.json` | machine comparison of all five windows (MTC and legacy) |
| `teleport/window.json` | legacy skill × teleport, as produced |
| `detachable_joint/window.json` | legacy skill × joint, as produced |
| `<backend>/<run>/skills/*.jsonl` | the verify/pick/place rows the report reads |

| window | skill | carry | worst verified error | verdict |
| --- | --- | --- | --- | --- |
| MTC × teleport | MTC | teleport | 0.171 mm | pass |
| MTC × velocity servo | MTC | velocity servo | 0.230 mm | pass |
| MTC × joint | MTC | joint | 12.252 mm | pass |
| legacy × teleport | legacy | teleport | 12.206 mm | pass |
| legacy × joint | legacy | joint | **45.007 mm** | pass (60 mm tolerance) |

Tolerance: one value, 60 mm, everywhere — no change. Failure codes: `ERR_NONE` on the four
passing cases, `ERR_RECOVERY_EXHAUSTED` on the declared negative, identical in every window.

The finding is the spread, not the verdict: the skill backend dominates the error (legacy ×
joint is within 15 mm of the tolerance), which qualifies the "joint is ~10x worse" statement
in #80/#81 to "within `skill_backend=mtc`".

Reproduce (one window):

```bash
python3 scripts/sim_window.py --manifest infra/legacy-parity-window.json \
  --out /tmp/legacy-teleport --backend teleport --skill-backend legacy
PYTHONPATH=scripts python3 scripts/parity_report.py /tmp/legacy-teleport/window.json \
  /tmp/legacy-joint/window.json
```

Run on the local stack because GitHub Actions is still refusing to start jobs; the CI job
`legacy-skill-matrix-smoke` runs the same two windows and the same comparison.
