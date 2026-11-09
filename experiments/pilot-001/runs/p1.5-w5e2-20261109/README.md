# W5-E2 — 真实 Gazebo 自改进试点（n=1，**失败**）

协议：[`docs/W5E2_PREREGISTRATION.md`](../../../docs/W5E2_PREREGISTRATION.md)。

## 设计
- 工作区 `config/week1.yaml` 注入缺陷：`zone_2_x = 0.45`（不可达）；
- 目标门：`dual_object` 真实 Gazebo 必须 PASS；
- 回归门：`normal` 必须 PASS；
- `gate/acceptance.py` 独立跑两门；`gate/` 为 protected。

## 结果（`result.json`）
| 项 | 值 |
| --- | --- |
| success | **false**（4 轮，8235 tokens） |
| agent 修改 | **未修改** `config/week1.yaml`（仍 0.45） |
| 目标门 | `ROBOT_FAILURE`（`PLACE_B` 失败，符合注入） |
| 回归门 | **PASS**（normal 不受影响） |
| 独立验收 | `passed=false` |

## 判读（按协议）
- 两门未同时 PASS → **非 verified improvement**；
- 失败原因是 **agent 未动手**（四轮均为读取，无 `write_file`），与 W6 Cold 观察一致；
- 目标门与回归门机制本身工作正常（目标失败/回归通过，fingerprint 一致）。

## 过程中修复的 harness 缺陷（非实验证据）
1. `--config-override` 未加入平台；已加（sim_smoke + sim_profile）；
2. W5A 工具集继承了 A 臂（缺 `run_execution`）；
3. `gazebo._wsl` 未把 `C:\...` 转成 `/mnt/c/...`（配置路径在 WSL 内不可读）；
4. 验收脚本缺 `tempfile` 导入。
