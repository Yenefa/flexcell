# 接手证据 — 2026-11-04

本目录只存**本机原始输出**，不是验收门禁、不接入 CI、不参与任何判定。
完整解释见 [`docs/TAKEOVER_20261104.md`](../../../docs/TAKEOVER_20261104.md)。

| 文件 | 来源 | 内容 |
| --- | --- | --- |
| `pr116-targeted-tests-windows.txt` | Windows，Python 3.13.14 / pytest 9.2.0 | PR #116 三个测试模块，`26 passed in 2.16s` |
| `pr116-targeted-tests-wsl.txt` | WSL Ubuntu-24.04 + ROS 2 Jazzy，Python 3.12.3 / pytest 7.4.4 | 同批测试，`26 passed in 0.82s` |
| `ci-gating-annotation.json` | `gh api repos/Yenefa/flexcell/check-runs/126446491046/annotations` | GitHub 账户付款 / spending limit 门禁的官方 annotation 原文 |

复现（在 `fix/camera-info-bridge` 分支）：

```bash
gh pr checkout 116 -R Yenefa/flexcell
python -m pytest \
  src/flexcell/flexcell_skills/test/test_camera_bridge.py \
  src/flexcell/flexcell_skills/test/test_s2_local.py \
  src/flexcell/flexcell_skills/test/test_three_object_scene.py -v
```

门禁证据复核：

```bash
gh api repos/Yenefa/flexcell/actions/runs/41791752178/jobs \
  --jq '.jobs[0] | {name,conclusion,runner_id,steps}'
gh api repos/Yenefa/flexcell/check-runs/126446491046/annotations
```

边界：这 26 项只覆盖 PR #116 的相机接线回归。本目录**不含**全量
`colcon test` 结果、不含新的 Gazebo 物理窗口、不含 GitHub CI 绿灯——
接手当日 GitHub Actions 因账户门禁在 0 step 被拒收，任何 checks 结果都不存在。
