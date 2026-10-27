# GRASP-B-001 Phase-3 gate — offline verification, 2026-10-26

Ref #32. Base `86bb4bded897fc90233896acfa629fb5a6623552`; runtime telemetry
dependency is reviewed PR #50, `be6684b30da1eafe80a585f84981a76a511ef48a`.
These are synthetic software checks. No Gazebo, model/GPU request or physical
hardware action was run. The grasp mechanism's physical root cause is UNKNOWN.

- `pytest.log` / `pytest.xml`: **112 passed**, including 75 new gate tests and
  4 new probe integration tests; the 33 existing grasp-probe tests also pass.
- `compat_pytest.log` / `compat_pytest.xml`: **137 passed** in a separate
  worktree based on #50 with this proposed change applied, adding its existing
  25 observation/loop differential tests to the same 112 related tests.
- `static_scan.log`: **37 files, 0 problems**.
- `summary.json`: exact commands, worktree paths, base/dependency commits and
  SHA-256 for the proposed probe, gate and two test files. Its paths describe
  this cloud workspace; reproduction can use any checkout location.

Reproduce the main-base check from the repository root:

```bash
PYTHONPATH=src/flexcell/flexcell_skills python3 -m pytest -q -o addopts='' \
  src/flexcell/flexcell_skills/test/test_carry_observation_gate.py \
  src/flexcell/flexcell_skills/test/test_grasp_probe.py
python3 setup/82_undefined_attr_check.py src/flexcell
```

For the compatibility check, use a separate checkout containing both the #50
commit and this proposed change, and add
`src/flexcell/flexcell_skills/test/test_carry_loop_observation.py` to the test
command. No production carry code was edited by this change.

The checks reject incomplete/ambiguous session evidence, contradictory action
results or measured poses, corrupt counter denominators, missing final/stop,
changed raw prefixes, malformed JSON and output overwrites. A typed physical
failure with complete evidence is retained; synthetic success cannot establish
the real TF/physics hypothesis. Full ROS CI and the new fixed diagnostic
window require separate evidence. See the
[simulation-host handoff](../../../docs/GRASP_PHASE3_GATE_20261026.md).
