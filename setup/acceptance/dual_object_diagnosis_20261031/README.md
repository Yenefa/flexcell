# Joint placement diagnosis — 2026-10-31

Four declared diagnostic runs that explain the joint backend's placement error. **Not
admission windows**: no gate, no tolerance claim, one task each. Read
`docs/JOINT_PLACEMENT_DIAGNOSIS_20261031.md` for the reasoning.

| file | what it is |
| --- | --- |
| `manifest.json` | the failing `dual_object` case, 2 ms trace, default 12 mm release clearance |
| `manifest-clearance-0mm.json` / `-4mm` / `-50mm` | the same case at the other declared clearances |
| `decompose.py` | trace decomposition: release height, lateral error at release, landing error |
| `decomposition*.json` | its output for each run |
| `trial-result*.json`, `skills*/`, `world*.sdf`, `params.yaml` | the runs as produced |

```bash
python3 scripts/sim_window.py --manifest setup/acceptance/dual_object_diagnosis_20261031/manifest-clearance-4mm.json \
  --out /tmp/dual-4mm --backend detachable_joint --skill-backend mtc
python3 setup/acceptance/dual_object_diagnosis_20261031/decompose.py /tmp/dual-4mm/trial-01/run-*
```

| declared clearance | object | release height | lateral at release | landed error | landed magnitude |
| --- | --- | --- | --- | --- | --- |
| 0 mm | A / B | +1.24 / +1.27 mm | +0.23/−0.23 / +0.17/+0.06 mm | +1.05/−1.37 / +0.72/+0.18 mm | 1.73 / 0.74 mm |
| 4 mm | A / B | +4.31 / +4.25 mm | +0.01/−0.14 / +0.03/+0.09 mm | +0.91/−1.40 / +0.68/+0.27 mm | 1.67 / 0.73 mm |
| 12 mm | A / B | +12.47 / +12.38 mm | +0.11/−0.04 / −0.02/−0.01 mm | +1.32/−1.71 / +2.67/+0.41 mm | 2.16 / 2.70 mm |
| 50 mm | A / B | +50.03 / +50.43 mm | +0.01/−0.00 / +0.03/+0.02 mm | −2.26/+3.15 / +9.43/+1.45 mm | 3.88 / 9.54 mm |

Release accuracy is ≤0.23 mm in every run; the placement error is created after release,
and it has two parts: a **floor of 0.7–1.7 mm that survives with no drop at all**, and a
**drop-dependent part** that grows with the declared clearance. Lowering the clearance
helps but cannot reach legacy accuracy (0.013–0.230 mm).

Note on the trace: the first attached frame is not usable (the joint exists one step
before the constraint settles). `decompose.py` takes the longest contiguous attached span
instead; without that, a 0.12 m drift appears that never happened.
