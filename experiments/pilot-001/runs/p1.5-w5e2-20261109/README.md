# W5-E2 — 真实 Gazebo 自改进，2 次试点（均**失败**）

协议：[`docs/W5E2_PREREGISTRATION.md`](../../../docs/W5E2_PREREGISTRATION.md)。
注入缺陷：工作区 `config/week1.yaml` 的 `zone_2_x=0.45`（不可达）。

| pilot | success | iters | tokens | 是否修改 config | 目标门 | 回归门 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | ❌ | 4 | 8235 | 否 | `ROBOT_FAILURE` | PASS |
| 2（新增 `edit_file` + 迭代提示后） | ❌ | 4 | 8709 | 否 | `ROBOT_FAILURE` | PASS |

## 判读
- 两次都是 **agent 未修改配置**（`PLACE_B` 失败、normal 通过），不是改错，也不是验收器问题；
- 新增的 `edit_file` 工具和"迭代/未修改"提示**没有改变**该任务上的行为；
- 结论：W5-E2 目前**未验证**；不能宣称真实 Gazebo 自改进闭环成立；
- 该"只读不写"现象在 W6 Cold（0/3）与 W5B（合成层）中也出现，已作为独立研究问题记录。

## 相关 harness 修复（非实验证据）
1. `--config-override` 平台杠杆；
2. W5A 工具集缺 `run_execution`；
3. `_wsl` 未转 `C:\` → `/mnt/c/`；
4. 验收脚本缺 `tempfile`；
5. 新增 `edit_file`（单次匹配）与迭代进度提示。
