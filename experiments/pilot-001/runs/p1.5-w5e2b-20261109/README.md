# W5-E2b — 真实 Gazebo 自改进 **成功**（n=1）

协议：[`docs/W5E2B_PREREGISTRATION.md`](../../../docs/W5E2B_PREREGISTRATION.md)。
相对 W5-E2：预算 6 轮、任务说明明确"`gate/` 只读、缺陷是 `config/week1.yaml` 的单个值"。

| 项 | 值 |
| --- | --- |
| success | **true** |
| 迭代 / tokens | **5 / 5161** |
| agent 修改 | `zone_2_x` 0.45 → 0.25（`edit_file`） |
| 目标门 | **PASS** |
| 回归门 | **PASS** |
| 独立验收 | `passed=true` |

## 闭环
`执行失败 → 读证据 → 定位（reach 0.4528 > 0.30）→ 修改配置 → 目标门 PASS → 回归门 PASS`，
两门均由 `gate/acceptance.py` 独立跑真实 Gazebo 判定；`gate/` 未被修改（hash 守卫）。

## 限制
- **n=1**；一个任务、一个模型；
- 任务缺陷是人工注入的受控实验，不是自发发现；
- 与 W5-E2（≤3 轮）对比时注意：E2b 是重新预注册（预算与提示不同）。

## 记录
- `transcript.md`：每轮 assistant 文本与工具结果；
- `aggregate.json`：含 result/verdict 的 SHA-256。
