# Static attribute scanner repair — 2026-10-07

Issue: [#24](https://github.com/Yenefa/flexcell/issues/24). Source baseline:
`ffde775a0ef9d1cb0f6a3b39436fbe1f97927370`. This repairs verification tooling;
no architecture decision or robot runtime change is involved.

## Reproduced defects

The baseline scanner reports five files with missing attributes in the current
35-file source tree. These are legitimate class constants, backend names and
the inherited ROS `create_service` method. Its definitions are pooled across
each file, so another class or a module-level function can also hide a real
missing instance member. Finally, the script exits **0 even when it reports
missing attributes**, making the existing CI step ineffective as a failure gate.

## Repair

- Collect methods, class declarations and instance assignments per class.
- Resolve local and imported source bases, including relative imports, aliases,
  transitive inheritance and multiple inheritance, without importing source code.
- Apply the known ROS Node API only to classes inheriting `rclpy.node.Node`, and
  include `create_service` in that API.
- Keep nested classes, function locals and comprehension variables separate.
- Return **1** for missing members and **2** for invalid, unreadable or empty
  source roots or invalid Python; return **0** for a clean scan. Diagnostics now
  identify the affected class. The existing CI command needs no workflow change.

This remains a declaration check. It does not prove that initialization happens
on every control-flow path or in the right order. External base definitions are
not imported; the explicit ROS Node API is the supported external exception.

## Verification — E-022

Evidence: [`setup/acceptance/issue24_static_scan_20261007/`](../setup/acceptance/issue24_static_scan_20261007/).
The machine-readable record includes exact commands, selected and excluded test
files, source hashes, the source baseline and process exit codes.

- **Before:** 35 source files, five reported files, exit 0.
- **After:** 35 source files, zero reported files, exit 0.
- **Planted ghost:** `self._gate.set_attach()` is reported, exit 1.
- **Tests:** 172 passed, zero failures/errors/skips, including 20 new scanner
  regressions. The new cases cover real CLI exit codes, valid class members,
  sibling/module/function scope isolation, nested classes, source inheritance,
  ROS API restrictions, excluded test directories and invalid scan inputs.

The selected suite runs on Python 3.12 without ROS. Eleven ROS-dependent test
files were excluded, including tests that import ROS only inside a fixture or
test body. Earlier broader attempts encountered missing `rclpy` and
`geometry_msgs`; those dependency errors are not counted as successful tests.
ROS/colcon builds, the complete ROS test suite and Gazebo acceptance batteries
are **NOT_RUN** in this cloud environment. The new regressions are under the
existing `test_*.py` configuration and will run in ROS CI.

**CI follow-up:** PR [#27](https://github.com/Yenefa/flexcell/pull/27) passed
the [ROS Jazzy workflow](https://github.com/Yenefa/flexcell/actions/runs/37665173778):
both packages built, **246 tests / 0 errors / 0 failures / 0 skipped**, and
35 scanned source files with zero missing attributes. It was merged as
`a9b6a6255d91a568e44eea555ecb33f7e0d7d49f`. This is separate CI evidence;
Gazebo runtime acceptance was not part of that workflow.

To repeat the scanner and its dedicated suite from the repository root:

```bash
python3 setup/82_undefined_attr_check.py src/flexcell
python3 -m pytest -o addopts= -q src/flexcell/flexcell_skills/test/test_undefined_attr_check.py
```
