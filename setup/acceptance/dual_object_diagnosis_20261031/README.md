# Joint placement diagnosis — 2026-10-31

Two declared diagnostic runs that explain the joint backend's placement error. **Not
admission windows**: no gate, no tolerance claim, one task each. Read
`docs/JOINT_PLACEMENT_DIAGNOSIS_20261031.md` for the reasoning.

| file | what it is |
| --- | --- |
| `manifest.json` | the failing `dual_object` case, 2 ms trace declared, default 12 mm release clearance |
| `manifest-clearance-50mm.json` | same case, declared 50 mm release clearance (perturbation) |
| `decompose.py` | trace decomposition: release height, lateral error at release, landing error |
| `decomposition.json`, `decomposition-clearance-50mm.json` | its output for both runs |
| `trial-result*.json`, `skills*/`, `world*.sdf` | the runs as produced (pick/place/verify/carry rows) |

Summary:

| run | object | release height | lateral at release | landed error |
| --- | --- | --- | --- | --- |
| 12 mm | A | +12.47 mm | +0.11 / −0.04 mm | +1.32 / −1.71 mm |
| 12 mm | B | +12.38 mm | −0.02 / −0.01 mm | +2.67 / +0.41 mm |
| 50 mm | A | +50.03 mm | +0.01 / −0.00 mm | −2.26 / +3.15 mm |
| 50 mm | B | +50.43 mm | +0.03 / +0.02 mm | +9.43 / +1.45 mm |

Release accuracy is ≤0.11 mm; the error is created by the landing after the declared
drop, and it grows with the drop height.

Note on the trace: the first attached frame is not usable (the joint exists one step
before the constraint settles). `decompose.py` takes the longest contiguous attached
span instead; without that, a 0.12 m drift appears that never happened.
