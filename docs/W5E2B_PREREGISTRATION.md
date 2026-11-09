# W5-E2b 预注册 — 真实 Gazebo 自改进（预算与提示修订版）

> 背景：W5-E2（≤3 迭代）3 次试点均失败，归因显示 agent 诊断正确但把预算全用于探索；
> 按资源规则判 BLOCKED。E2b 是**重新预注册**，不是对原协议的事后修改。

## 1. 相对 E2 的唯一变化
| 项 | W5-E2 | W5-E2b |
| --- | --- | --- |
| 最大迭代 | 4 | **6** |
| task.md | 只说"修 config/week1.yaml" | 明确"`gate/` 只读、**无需查看**；缺陷是 `config/week1.yaml` 中 `zone_2` 的单个值"；
| 其余 | 缺陷、双门、protected、模型、超时 | **完全相同** |

## 2. 双门（不变）
1. 目标门：`dual_object` 真实 Gazebo PASS；
2. 回归门：`normal` PASS；
3. `gate/` protected；两门由 `gate/acceptance.py` 独立执行。

## 3. 指标与判读（冻结）
- 主指标：两门同时 PASS（verified improvement）；
- 次指标：迭代数、token、wall；
- 若仍失败：记录并**不再继续加预算**（最多 3 次 E2b 试点），避免无限调参；
- 不宣称"系统已能自我进化"，只记录本次闭环。

## 4. 记录位置
- `experiments/pilot-001/runs/p1.5-w5e2b-20261109/`。

## 5. 结果附录（运行后追加，不改规则）
- **成功**：5 轮、5161 tokens；目标门 PASS、回归门 PASS、独立验收 `passed=true`；
- agent 用 `edit_file` 把 `zone_2_x` 0.45 → 0.25；`gate/` 未修改；
- 记录：`experiments/pilot-001/runs/p1.5-w5e2b-20261109/`（含 `transcript.md`、`verify.py`）；
- 期间发现并修正一个**任务缺陷注入 bug**：原注入误改旧键 `zone_zone_2_x` 且留下两处不可一次修复；改为最小覆盖文件。
