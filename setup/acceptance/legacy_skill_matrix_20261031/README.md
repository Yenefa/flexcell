# Legacy skill matrix — 2026-10-31

`skill_backend=legacy` on both carry backends, same five declared tasks and same 60 mm
verifier tolerance as the MTC windows. Read `docs/LEGACY_SKILL_MATRIX_20261031.md`.

| file | what it is |
| --- | --- |
| `matrix-report.json` | machine comparison of all five windows (MTC and legacy) |
| `teleport/window.json` | legacy skill × teleport, as produced |
| `detachable_joint/window.json` | legacy skill × joint, as produced |
| `detachable_joint_repeat/` | the declared repeat of the thinnest cell, same manifest |
| `repeat-report.json` | both joint × legacy windows side by side, with the spread |
| `<backend>/<run>/skills/*.jsonl` | the verify/pick/place rows the reports read |

| window | skill | carry | worst verified error | verdict |
| --- | --- | --- | --- | --- |
| MTC × teleport | MTC | teleport | 0.171 mm | pass |
| MTC × velocity servo | MTC | velocity servo | 0.230 mm | pass |
| MTC × joint | MTC | joint | 12.252 mm | pass |
| legacy × teleport | legacy | teleport | 12.206 mm | pass |
| legacy × joint (run 1) | legacy | joint | **45.007 mm** | pass (60 mm) |
| legacy × joint (run 2) | legacy | joint | 34.829 mm | pass (60 mm) |

Tolerance: one value, 60 mm, everywhere — no change. Failure codes: `ERR_NONE` on the four
passing cases, `ERR_RECOVERY_EXHAUSTED` on the declared negative, identical in every window.

The finding is the spread, not the verdict. The skill backend dominates the error, and the
thinnest cell was repeated to check whether its 45 mm was luck:

| case | joint × legacy run 1 | run 2 |
| --- | --- | --- |
| normal / A | 19.808 mm | 34.829 mm |
| normal / B | 21.894 mm | 22.816 mm |
| dual_object | 27.596 / 45.007 mm | 24.851 / 33.915 mm |
| recovery_once | 18.376 mm | 27.625 mm |

Ten placements across both windows: **18.4–45.0 mm, mean 27.7 mm, worst at 75 % of the
tolerance**. Repeatably passing, but with the thinnest margin measured in this project —
any tolerance below ~46 mm would have rejected it.

Reproduce (one window):

```bash
python3 scripts/sim_window.py --manifest infra/legacy-parity-window.json \
  --out /tmp/legacy-joint --backend detachable_joint --skill-backend legacy
PYTHONPATH=scripts python3 scripts/parity_report.py /tmp/legacy-teleport/window.json \
  /tmp/legacy-joint/window.json
```

Run on the local stack because GitHub Actions is still refusing to start jobs; the CI job
`legacy-skill-matrix-smoke` runs the same two windows and the same comparison.
